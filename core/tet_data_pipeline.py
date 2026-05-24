from loguru import logger
"""
TET数据管道实现
Transform-Extract-Transform数据处理管道
借鉴OpenBB架构设计，为FactorWeave-Quant提供标准化多资产数据支持

增强版本：支持多数据源路由、故障转移、插件化数据源
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from .plugin_types import AssetType, DataType
from .data_source_router import DataSourceRouter, RoutingRequest, RoutingStrategy
from .data_source_extensions import IDataSourcePlugin, DataSourcePluginAdapter, HealthCheckResult
# NOTE: FieldMappingEngine使用延迟导入避免循环依赖
# from .data.field_mapping_engine import FieldMappingEngine



@dataclass
class StandardQuery:
    """标准化查询请求"""
    symbol: str
    asset_type: AssetType
    data_type: DataType
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "D"
    market: Optional[str] = None
    provider: Optional[str] = None  # 指定数据源
    extra_params: Dict[str, Any] = field(default_factory=dict)

    # 路由相关参数
    priority: int = 0
    timeout_ms: int = 5000
    retry_count: int = 3
    fallback_enabled: bool = True

    def __post_init__(self):
        """后处理初始化"""
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class StandardData:
    """标准化数据输出"""
    data: pd.DataFrame
    metadata: Dict[str, Any]
    source_info: Dict[str, Any]
    query: StandardQuery
    processing_time_ms: float = 0.0
    success: bool = True  # 处理是否成功
    error_message: Optional[str] = None  # 错误信息（如有）


@dataclass
class FailoverResult:
    """故障转移结果"""
    success: bool
    attempts: int
    failed_sources: List[str]
    successful_source: Optional[str]
    error_messages: List[str]
    total_time_ms: float


class TETDataPipeline:
    """
    TET数据管道实现
    Transform-Extract-Transform三阶段数据处理

    增强功能：
    - 多数据源路由和负载均衡
    - 智能故障转移
    - 插件化数据源支持
    - 异步并发处理
    - 缓存和性能优化
    """

    def __init__(self, data_source_router: DataSourceRouter):
        self.router = data_source_router
        self.logger = logger  # 添加logger属性初始化
        
        # 插件管理
        self._plugins: Dict[str, IDataSourcePlugin] = {}
        self._adapters: Dict[str, DataSourcePluginAdapter] = {}

        # 缓存管理
        self._cache: Dict[str, Tuple[StandardData, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)  # 缓存5分钟

        # 异步处理
        self._executor = ThreadPoolExecutor(max_workers=4)

        # 性能统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "avg_processing_time": 0.0
        }

        # 字段映射表（用于数据标准化）
        self.field_mappings = {
            # OHLCV标准化映射
            DataType.HISTORICAL_KLINE: {
                # 开盘价
                'o': 'open', 'Open': 'open', 'OPEN': 'open', '开盘价': 'open', 'opening': 'open',
                # 最高价
                'h': 'high', 'High': 'high', 'HIGH': 'high', '最高价': 'high', 'highest': 'high',
                # 最低价
                'l': 'low', 'Low': 'low', 'LOW': 'low', '最低价': 'low', 'lowest': 'low',
                # 收盘价
                'c': 'close', 'Close': 'close', 'CLOSE': 'close', '收盘价': 'close', 'closing': 'close',
                # 成交量
                'v': 'volume', 'Volume': 'volume', 'VOLUME': 'volume', '成交量': 'volume', 'vol': 'volume',
                # 成交额
                'amount': 'amount', 'Amount': 'amount', 'AMOUNT': 'amount', '成交额': 'amount', 'turnover': 'amount',
                # 日期/时间
                't': 'datetime', 'time': 'datetime', 'Time': 'datetime', 'timestamp': 'datetime', 'date': 'datetime', '日期': 'datetime',
                # 其他常见字段
                'vwap': 'vwap', 'VWAP': 'vwap', 'adj_close': 'adj_close'
            },

            # 实时数据映射
            DataType.REAL_TIME_QUOTE: {
                # 基础价格字段
                'price': 'current_price', 'current': 'current_price', 'last': 'current_price', '现价': 'current_price',
                'bid': 'bid_price', 'bid_price': 'bid_price', '买一价': 'bid_price',
                'ask': 'ask_price', 'ask_price': 'ask_price', '卖一价': 'ask_price',
                'open': 'open_price', 'open_price': 'open_price', '开盘价': 'open_price',
                'high': 'high_price', 'high_price': 'high_price', '最高价': 'high_price',
                'low': 'low_price', 'low_price': 'low_price', '最低价': 'low_price',
                'close': 'prev_close', 'prev_close': 'prev_close', '昨收价': 'prev_close',

                # 成交量和成交额
                'volume': 'volume', 'vol': 'volume', '成交量': 'volume',
                'amount': 'turnover', 'turnover': 'turnover', '成交额': 'turnover',

                # 涨跌相关
                'change': 'change', 'chg': 'change', '涨跌额': 'change',
                'change_pct': 'change_percent', 'pct_chg': 'change_percent', '涨跌幅': 'change_percent',

                # 时间戳
                'timestamp': 'update_time', 'time': 'update_time', 'update_time': 'update_time', '更新时间': 'update_time'
            },

            # Stage 3 新增：财务报表数据映射
            DataType.FINANCIAL_STATEMENT: {
                # 资产负债表字段映射
                'total_assets': 'total_assets', '资产总计': 'total_assets', '总资产': 'total_assets',
                'current_assets': 'current_assets', '流动资产': 'current_assets', '流动资产合计': 'current_assets',
                'non_current_assets': 'non_current_assets', '非流动资产': 'non_current_assets', '非流动资产合计': 'non_current_assets',
                'cash_and_equivalents': 'cash_and_equivalents', '货币资金': 'cash_and_equivalents', '现金及现金等价物': 'cash_and_equivalents',
                'accounts_receivable': 'accounts_receivable', '应收账款': 'accounts_receivable', '应收账款净额': 'accounts_receivable',
                'inventory': 'inventory', '存货': 'inventory', '存货净额': 'inventory',
                'fixed_assets': 'fixed_assets', '固定资产': 'fixed_assets', '固定资产净额': 'fixed_assets',

                'total_liabilities': 'total_liabilities', '负债总计': 'total_liabilities', '总负债': 'total_liabilities',
                'current_liabilities': 'current_liabilities', '流动负债': 'current_liabilities', '流动负债合计': 'current_liabilities',
                'non_current_liabilities': 'non_current_liabilities', '非流动负债': 'non_current_liabilities', '非流动负债合计': 'non_current_liabilities',
                'accounts_payable': 'accounts_payable', '应付账款': 'accounts_payable', '应付账款余额': 'accounts_payable',
                'short_term_debt': 'short_term_debt', '短期借款': 'short_term_debt', '短期债务': 'short_term_debt',
                'long_term_debt': 'long_term_debt', '长期借款': 'long_term_debt', '长期债务': 'long_term_debt',

                'shareholders_equity': 'shareholders_equity', '股东权益': 'shareholders_equity', '净资产': 'shareholders_equity',
                'paid_in_capital': 'paid_in_capital', '实收资本': 'paid_in_capital', '股本': 'paid_in_capital',
                'retained_earnings': 'retained_earnings', '留存收益': 'retained_earnings', '未分配利润': 'retained_earnings',

                # 利润表字段映射
                'operating_revenue': 'operating_revenue', '营业收入': 'operating_revenue', 'revenue': 'operating_revenue', '总收入': 'operating_revenue',
                'operating_costs': 'operating_costs', '营业成本': 'operating_costs', 'cost_of_sales': 'operating_costs',
                'gross_profit': 'gross_profit', '毛利润': 'gross_profit', '毛利': 'gross_profit',
                'operating_expenses': 'operating_expenses', '营业费用': 'operating_expenses', '期间费用': 'operating_expenses',
                'selling_expenses': 'selling_expenses', '销售费用': 'selling_expenses', '销售成本': 'selling_expenses',
                'admin_expenses': 'admin_expenses', '管理费用': 'admin_expenses', '管理成本': 'admin_expenses',
                'rd_expenses': 'rd_expenses', '研发费用': 'rd_expenses', 'r_and_d': 'rd_expenses',
                'financial_expenses': 'financial_expenses', '财务费用': 'financial_expenses', '利息费用': 'financial_expenses',
                'operating_profit': 'operating_profit', '营业利润': 'operating_profit', '经营利润': 'operating_profit',
                'profit_before_tax': 'profit_before_tax', '利润总额': 'profit_before_tax', '税前利润': 'profit_before_tax',
                'income_tax': 'income_tax', '所得税费用': 'income_tax', '税费': 'income_tax',
                'net_profit': 'net_profit', '净利润': 'net_profit', 'profit': 'net_profit', '净收益': 'net_profit',
                'net_profit_attributable_to_parent': 'net_profit_attributable_to_parent', '归母净利润': 'net_profit_attributable_to_parent',

                'eps': 'eps', '每股收益': 'eps', 'earnings_per_share': 'eps', '基本每股收益': 'eps',
                'diluted_eps': 'diluted_eps', '稀释每股收益': 'diluted_eps', '摊薄每股收益': 'diluted_eps',
                'book_value_per_share': 'book_value_per_share', '每股净资产': 'book_value_per_share', '每股账面价值': 'book_value_per_share',

                # 现金流量表字段映射
                'operating_cash_flow': 'operating_cash_flow', '经营现金流': 'operating_cash_flow', 'ocf': 'operating_cash_flow', '经营活动现金流量净额': 'operating_cash_flow',
                'investing_cash_flow': 'investing_cash_flow', '投资现金流': 'investing_cash_flow', 'icf': 'investing_cash_flow', '投资活动现金流量净额': 'investing_cash_flow',
                'financing_cash_flow': 'financing_cash_flow', '筹资现金流': 'financing_cash_flow', 'fcf': 'financing_cash_flow', '筹资活动现金流量净额': 'financing_cash_flow',
                'net_cash_flow': 'net_cash_flow', '现金流量净额': 'net_cash_flow', '现金净增加额': 'net_cash_flow',
                'free_cash_flow': 'free_cash_flow', '自由现金流': 'free_cash_flow', '自由现金流量': 'free_cash_flow',

                # 财务比率字段映射
                'roe': 'roe', '净资产收益率': 'roe', 'return_on_equity': 'roe',
                'roa': 'roa', '总资产收益率': 'roa', 'return_on_assets': 'roa',
                'roic': 'roic', '投入资本回报率': 'roic', 'return_on_invested_capital': 'roic',
                'gross_profit_margin': 'gross_profit_margin', '毛利率': 'gross_profit_margin', '毛利润率': 'gross_profit_margin',
                'net_profit_margin': 'net_profit_margin', '净利率': 'net_profit_margin', '净利润率': 'net_profit_margin',
                'current_ratio': 'current_ratio', '流动比率': 'current_ratio', '流动性比率': 'current_ratio',
                'quick_ratio': 'quick_ratio', '速动比率': 'quick_ratio', '酸性测试比率': 'quick_ratio',
                'debt_to_equity': 'debt_to_equity', '负债权益比': 'debt_to_equity', '债务权益比': 'debt_to_equity',
                'debt_to_assets': 'debt_to_assets', '资产负债率': 'debt_to_assets', '负债比率': 'debt_to_assets',
                'asset_liability_ratio': 'asset_liability_ratio', '资产负债比': 'asset_liability_ratio'
            },

            # Stage 3 新增：宏观经济数据映射
            DataType.MACRO_ECONOMIC: {
                # GDP相关指标
                'gdp': 'gdp', 'GDP': 'gdp', '国内生产总值': 'gdp', 'gross_domestic_product': 'gdp',
                'gdp_yoy': 'gdp_yoy', 'GDP同比': 'gdp_yoy', 'GDP同比增长率': 'gdp_yoy', 'gdp_growth': 'gdp_yoy',
                'gdp_qoq': 'gdp_qoq', 'GDP环比': 'gdp_qoq', 'GDP环比增长率': 'gdp_qoq',

                # 价格指数
                'cpi': 'cpi', 'CPI': 'cpi', '消费者价格指数': 'cpi', 'consumer_price_index': 'cpi',
                'cpi_yoy': 'cpi_yoy', 'CPI同比': 'cpi_yoy', 'CPI同比增长率': 'cpi_yoy',
                'ppi': 'ppi', 'PPI': 'ppi', '生产者价格指数': 'ppi', 'producer_price_index': 'ppi',
                'ppi_yoy': 'ppi_yoy', 'PPI同比': 'ppi_yoy', 'PPI同比增长率': 'ppi_yoy',

                # 利率相关
                'interest_rate': 'interest_rate', '利率': 'interest_rate', 'rate': 'interest_rate',
                'benchmark_rate': 'benchmark_rate', '基准利率': 'benchmark_rate', '央行利率': 'benchmark_rate',
                'deposit_rate': 'deposit_rate', '存款利率': 'deposit_rate', '存款基准利率': 'deposit_rate',
                'lending_rate': 'lending_rate', '贷款利率': 'lending_rate', '贷款基准利率': 'lending_rate',

                # 汇率相关
                'exchange_rate': 'exchange_rate', '汇率': 'exchange_rate', 'fx_rate': 'exchange_rate',
                'usd_cny': 'usd_cny', '美元人民币': 'usd_cny', 'USDCNY': 'usd_cny',
                'eur_cny': 'eur_cny', '欧元人民币': 'eur_cny', 'EURCNY': 'eur_cny',

                # 货币供应量
                'money_supply': 'money_supply', '货币供应量': 'money_supply', 'money_stock': 'money_supply',
                'm0': 'm0', 'M0': 'm0', '流通中货币': 'm0',
                'm1': 'm1', 'M1': 'm1', '狭义货币': 'm1',
                'm2': 'm2', 'M2': 'm2', '广义货币': 'm2',

                # 就业指标
                'unemployment_rate': 'unemployment_rate', '失业率': 'unemployment_rate', '城镇失业率': 'unemployment_rate',
                'employment_rate': 'employment_rate', '就业率': 'employment_rate', '就业人数': 'employment_rate',

                # 贸易指标
                'trade_balance': 'trade_balance', '贸易差额': 'trade_balance', '贸易顺差': 'trade_balance',
                'exports': 'exports', '出口': 'exports', '出口总额': 'exports',
                'imports': 'imports', '进口': 'imports', '进口总额': 'imports',

                # PMI指标
                'pmi': 'pmi', 'PMI': 'pmi', '采购经理指数': 'pmi', 'purchasing_managers_index': 'pmi',
                'manufacturing_pmi': 'manufacturing_pmi', '制造业PMI': 'manufacturing_pmi', '制造业采购经理指数': 'manufacturing_pmi',
                'services_pmi': 'services_pmi', '服务业PMI': 'services_pmi', '服务业采购经理指数': 'services_pmi',

                # 工业指标
                'industrial_production': 'industrial_production', '工业增加值': 'industrial_production', '工业生产指数': 'industrial_production',
                'industrial_production_yoy': 'industrial_production_yoy', '工业增加值同比': 'industrial_production_yoy',

                # 投资指标
                'fixed_asset_investment': 'fixed_asset_investment', '固定资产投资': 'fixed_asset_investment', '固投': 'fixed_asset_investment',
                'fixed_asset_investment_yoy': 'fixed_asset_investment_yoy', '固定资产投资同比': 'fixed_asset_investment_yoy',

                # 消费指标
                'retail_sales': 'retail_sales', '社会消费品零售总额': 'retail_sales', '零售销售': 'retail_sales',
                'retail_sales_yoy': 'retail_sales_yoy', '社会消费品零售总额同比': 'retail_sales_yoy',

                # 通用字段
                'value': 'value', '数值': 'value', '指标值': 'value',
                'unit': 'unit', '单位': 'unit', '计量单位': 'unit',
                'frequency': 'frequency', '频率': 'frequency', '数据频率': 'frequency',
                'category': 'category', '分类': 'category', '指标分类': 'category',
                'indicator_code': 'indicator_code', '指标代码': 'indicator_code', '代码': 'indicator_code',
                'indicator_name': 'indicator_name', '指标名称': 'indicator_name', '名称': 'indicator_name'
            },

            # 新增：板块资金流数据映射
            DataType.SECTOR_FUND_FLOW: {
                # 板块基础信息
                'sector_id': 'sector_id', '板块ID': 'sector_id', 'sector_code': 'sector_id', '板块代码': 'sector_id',
                'sector_name': 'sector_name', '板块名称': 'sector_name', '板块': 'sector_name', 'name': 'sector_name',
                'code': 'sector_code', 'sector_code': 'sector_code', '代码': 'sector_code',

                # 主力资金流
                'main_inflow': 'main_inflow', '主力流入': 'main_inflow', '主力买入': 'main_inflow', 'main_buy': 'main_inflow',
                'main_outflow': 'main_outflow', '主力流出': 'main_outflow', '主力卖出': 'main_outflow', 'main_sell': 'main_outflow',
                'main_net_inflow': 'main_net_inflow', '主力净流入': 'main_net_inflow', '主力净买入': 'main_net_inflow', 'main_net': 'main_net_inflow',

                # 散户资金流
                'retail_inflow': 'retail_inflow', '散户流入': 'retail_inflow', '散户买入': 'retail_inflow', 'retail_buy': 'retail_inflow',
                'retail_outflow': 'retail_outflow', '散户流出': 'retail_outflow', '散户卖出': 'retail_outflow', 'retail_sell': 'retail_outflow',
                'retail_net_inflow': 'retail_net_inflow', '散户净流入': 'retail_net_inflow', '散户净买入': 'retail_net_inflow', 'retail_net': 'retail_net_inflow',

                # 大单资金流
                'large_order_inflow': 'large_order_inflow', '大单流入': 'large_order_inflow', '大单买入': 'large_order_inflow', 'large_buy': 'large_order_inflow',
                'large_order_outflow': 'large_order_outflow', '大单流出': 'large_order_outflow', '大单卖出': 'large_order_outflow', 'large_sell': 'large_order_outflow',
                'large_order_net_inflow': 'large_order_net_inflow', '大单净流入': 'large_order_net_inflow', '大单净买入': 'large_order_net_inflow', 'large_net': 'large_order_net_inflow',

                # 中单资金流
                'medium_order_inflow': 'medium_order_inflow', '中单流入': 'medium_order_inflow', '中单买入': 'medium_order_inflow', 'medium_buy': 'medium_order_inflow',
                'medium_order_outflow': 'medium_order_outflow', '中单流出': 'medium_order_outflow', '中单卖出': 'medium_order_outflow', 'medium_sell': 'medium_order_outflow',
                'medium_order_net_inflow': 'medium_order_net_inflow', '中单净流入': 'medium_order_net_inflow', '中单净买入': 'medium_order_net_inflow', 'medium_net': 'medium_order_net_inflow',

                # 小单资金流
                'small_order_inflow': 'small_order_inflow', '小单流入': 'small_order_inflow', '小单买入': 'small_order_inflow', 'small_buy': 'small_order_inflow',
                'small_order_outflow': 'small_order_outflow', '小单流出': 'small_order_outflow', '小单卖出': 'small_order_outflow', 'small_sell': 'small_order_outflow',
                'small_order_net_inflow': 'small_order_net_inflow', '小单净流入': 'small_order_net_inflow', '小单净买入': 'small_order_net_inflow', 'small_net': 'small_order_net_inflow',

                # 板块统计数据
                'stock_count': 'stock_count', '股票数量': 'stock_count', '成分股数量': 'stock_count', 'count': 'stock_count',
                'rise_count': 'rise_count', '上涨家数': 'rise_count', '涨股数': 'rise_count', 'up_count': 'rise_count',
                'fall_count': 'fall_count', '下跌家数': 'fall_count', '跌股数': 'fall_count', 'down_count': 'fall_count',
                'flat_count': 'flat_count', '平盘家数': 'flat_count', '平股数': 'flat_count', 'unchanged_count': 'flat_count',

                # 价格变动
                'avg_change_pct': 'avg_change_pct', '平均涨跌幅': 'avg_change_pct', '平均涨幅': 'avg_change_pct', 'avg_change': 'avg_change_pct',
                'change_pct': 'avg_change_pct', '涨跌幅': 'avg_change_pct', '涨幅': 'avg_change_pct', 'pct_change': 'avg_change_pct',

                # 成交数据
                'total_turnover': 'total_turnover', '总成交额': 'total_turnover', '成交额': 'total_turnover', 'turnover': 'total_turnover',
                'amount': 'total_turnover', '金额': 'total_turnover', 'volume_amount': 'total_turnover',

                # 排名数据
                'rank_by_amount': 'rank_by_amount', '按金额排名': 'rank_by_amount', '资金排名': 'rank_by_amount', 'amount_rank': 'rank_by_amount',
                'rank_by_ratio': 'rank_by_ratio', '按占比排名': 'rank_by_ratio', '占比排名': 'rank_by_ratio', 'ratio_rank': 'rank_by_ratio',
                'rank': 'rank_by_amount', '排名': 'rank_by_amount', 'ranking': 'rank_by_amount',

                # 时间字段
                'trade_date': 'trade_date', '交易日期': 'trade_date', '日期': 'trade_date', 'date': 'trade_date',
                'trade_time': 'trade_time', '交易时间': 'trade_time', '时间': 'trade_time', 'time': 'trade_time',
                'update_time': 'update_time', '更新时间': 'update_time', 'timestamp': 'update_time',

                # 元数据字段
                'data_source': 'data_source', '数据源': 'data_source', 'source': 'data_source', 'provider': 'data_source'
            }
        }

        # 空值表示（用于清理数据）
        self.null_values = ['N/A', 'null', 'NULL', '', 'nan', 'NaN', 'None', '--', '-']

        # Stage 3 新增：智能字段映射引擎（延迟导入避免循环依赖）
        try:
            from .data.field_mapping_engine import FieldMappingEngine
            self.field_mapping_engine = FieldMappingEngine(self.field_mappings)
        except ImportError as e:
            logger.warning(f"无法导入FieldMappingEngine，将使用基础映射: {e}")
            self.field_mapping_engine = None

    def register_plugin(self, plugin_id: str, plugin: IDataSourcePlugin) -> bool:
        """
        注册数据源插件

        Args:
            plugin_id: 插件唯一标识
            plugin: 插件实例

        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证插件接口
            from .data_source_extensions import validate_plugin_interface, create_plugin_adapter

            if not validate_plugin_interface(plugin):
                self.logger.error(f"插件接口验证失败: {plugin_id}")
                return False

            # 创建适配器
            adapter = create_plugin_adapter(plugin, plugin_id)
            if not adapter:
                self.logger.error(f"创建插件适配器失败: {plugin_id}")
                return False

            # 注册到路由器
            self.router.register_data_source(plugin_id, adapter)

            # 保存引用
            self._plugins[plugin_id] = plugin
            self._adapters[plugin_id] = adapter

            self.logger.info(f"数据源插件注册成功: {plugin_id}")
            return True

        except Exception as e:
            self.logger.error(f"注册数据源插件失败 {plugin_id}: {e}")
            return False

    def unregister_plugin(self, plugin_id: str) -> bool:
        """
        注销数据源插件

        Args:
            plugin_id: 插件唯一标识

        Returns:
            bool: 注销是否成功
        """
        try:
            # 从路由器注销
            self.router.unregister_data_source(plugin_id)

            # 断开连接
            if plugin_id in self._adapters:
                self._adapters[plugin_id].disconnect()
                del self._adapters[plugin_id]

            # 清理引用
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]

            self.logger.info(f"数据源插件注销成功: {plugin_id}")
            return True

        except Exception as e:
            self.logger.error(f"注销数据源插件失败 {plugin_id}: {e}")
            return False

    def process(self, query: StandardQuery) -> StandardData:
        """
        完整的TET流程处理

        Args:
            query: 标准化查询请求

        Returns:
            StandardData: 标准化处理结果

        Raises:
            Exception: 处理失败时抛出异常
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        try:
            self.logger.info(f"开始TET处理: {query.symbol} ({query.asset_type.value}) - {query.data_type.value}")

            # 检查缓存
            cache_key = self._generate_cache_key(query)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self._stats["cache_hits"] += 1
                self.logger.debug(f"缓存命中: {query.symbol}")
                return cached_result

            # Stage 1: Transform Query（查询转换）
            routing_request = self.transform_query(query)
            self.logger.debug(f"查询转换完成: asset_type={routing_request.asset_type.value}")

            # Stage 2: Extract Data（数据提取 - 支持故障转移）
            raw_data, provider_info, failover_result = self.extract_data_with_failover(routing_request, query)

            if failover_result and not failover_result.success:
                self.logger.error(f"下载股票数据失败: {query.symbol}")
                raise Exception(f"数据提取失败: {', '.join(failover_result.error_messages)}")

            self.logger.debug(f"数据提取完成: {len(raw_data) if raw_data is not None else 0} 条记录")

            # Stage 3: Transform Data（数据标准化）
            standard_data = self.transform_data(raw_data, query)
            self.logger.debug(f"数据标准化完成: {len(standard_data)} 条记录")

            processing_time = (time.time() - start_time) * 1000

            result = StandardData(
                data=standard_data,
                metadata=self._build_metadata(query, raw_data, failover_result),
                source_info=provider_info,
                query=query,
                processing_time_ms=processing_time
            )

            # 更新缓存
            self._set_to_cache(cache_key, result)

            # 更新统计
            self._update_stats(processing_time)

            self.logger.info(f"TET处理完成: {processing_time:.2f}ms")
            return result

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self.logger.error(f"TET处理失败 ({processing_time:.2f}ms): {e}")
            raise

    def transform_query(self, query: StandardQuery) -> RoutingRequest:
        """
        Stage 1: 查询转换
        将标准化查询转换为路由请求

        Args:
            query: 标准化查询

        Returns:
            RoutingRequest: 路由请求
        """
        return RoutingRequest(
            asset_type=query.asset_type,
            data_type=query.data_type,
            symbol=query.symbol,
            priority=query.priority,
            timeout_ms=query.timeout_ms,
            retry_count=query.retry_count,
            metadata={
                'period': query.period,
                'start_date': query.start_date,
                'end_date': query.end_date,
                'market': query.market,
                'provider': query.provider,
                **query.extra_params
            }
        )

    def extract_data_with_failover(self, routing_request: RoutingRequest,
                                   original_query: StandardQuery) -> Tuple[pd.DataFrame, Dict[str, Any], FailoverResult]:
        """
        Stage 2: 数据提取（支持故障转移）

        Args:
            routing_request: 路由请求
            original_query: 原始查询

        Returns:
            Tuple[pd.DataFrame, Dict[str, Any], FailoverResult]: (数据, 提供商信息, 故障转移结果)
        """
        start_time = time.time()
        failed_sources = []
        error_messages = []
        attempts = 0

        # 如果指定了特定提供商，直接使用，避免检查其他数据源
        if original_query.provider:
            # 检查指定的数据源是否存在
            if self.router.has_data_source(original_query.provider):
                available_sources = [original_query.provider]
                self.logger.info(f"使用指定的数据源: {original_query.provider}")
            else:
                failover_result = FailoverResult(
                    success=False,
                    attempts=0,
                    failed_sources=[],
                    successful_source=None,
                    error_messages=[f"指定的数据源不存在: {original_query.provider}"],
                    total_time_ms=(time.time() - start_time) * 1000
                )
                return pd.DataFrame(), {}, failover_result
        else:
            # 只有在没有指定数据源时才获取所有可用数据源
            available_sources = self.router.get_available_sources(routing_request)

            if not available_sources:
                failover_result = FailoverResult(
                    success=False,
                    attempts=0,
                    failed_sources=[],
                    successful_source=None,
                    error_messages=["没有可用的数据源"],
                    total_time_ms=(time.time() - start_time) * 1000
                )
                return pd.DataFrame(), {}, failover_result

        # 尝试每个数据源
        for source_id in available_sources:
            attempts += 1

            try:
                self.logger.debug(f"尝试数据源: {source_id} (第{attempts}次尝试)")

                # 获取数据源适配器
                adapter = self._adapters.get(source_id)
                if not adapter:
                    error_msg = f"数据源适配器不存在: {source_id}"
                    error_messages.append(error_msg)
                    failed_sources.append(source_id)
                    continue

                # 检查连接状态
                if not adapter.is_connected():
                    if not adapter.connect():
                        error_msg = f"数据源连接失败: {source_id}"
                        error_messages.append(error_msg)
                        failed_sources.append(source_id)
                        continue

                # 提取数据
                raw_data = self._extract_from_source(adapter, routing_request, original_query)

                if raw_data is not None and not raw_data.empty:
                    provider_info = {
                        'provider': source_id,
                        'plugin_info': adapter.get_plugin_info(),
                        'extraction_time': datetime.now().isoformat()
                    }

                    failover_result = FailoverResult(
                        success=True,
                        attempts=attempts,
                        failed_sources=failed_sources,
                        successful_source=source_id,
                        error_messages=error_messages,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

                    self.logger.info(f"数据提取成功: {source_id} (尝试{attempts}次)")
                    return raw_data, provider_info, failover_result
                else:
                    error_msg = f"数据源返回空数据: {source_id}"
                    error_messages.append(error_msg)
                    failed_sources.append(source_id)

            except Exception as e:
                error_msg = f"数据源异常 {source_id}: {str(e)}"
                error_messages.append(error_msg)
                failed_sources.append(source_id)
                self.logger.warning(error_msg)

        # 所有数据源都失败
        self._stats["fallback_used"] += 1

        failover_result = FailoverResult(
            success=False,
            attempts=attempts,
            failed_sources=failed_sources,
            successful_source=None,
            error_messages=error_messages,
            total_time_ms=(time.time() - start_time) * 1000
        )

        return pd.DataFrame(), {}, failover_result

    def _extract_from_source(self, adapter: DataSourcePluginAdapter,
                             routing_request: RoutingRequest,
                             original_query: StandardQuery) -> pd.DataFrame:
        """
        从指定数据源提取数据

        Args:
            adapter: 数据源适配器
            routing_request: 路由请求
            original_query: 原始查询

        Returns:
            pd.DataFrame: 提取的数据
        """
        if original_query.data_type == DataType.HISTORICAL_KLINE:
            return adapter.get_kdata(
                symbol=original_query.symbol,
                freq=original_query.period,
                start_date=original_query.start_date,
                end_date=original_query.end_date,
                count=original_query.extra_params.get('count')
            )
        elif original_query.data_type == DataType.REAL_TIME_QUOTE:
            return adapter.get_real_time_quotes([original_query.symbol])
        elif original_query.data_type == DataType.ASSET_LIST:
            # 获取资产列表
            asset_list = adapter.get_asset_list(
                asset_type=original_query.asset_type,
                market=original_query.market
            )
            # 转换为DataFrame
            if asset_list:
                return pd.DataFrame(asset_list)
            else:
                return pd.DataFrame()
        elif original_query.data_type == DataType.SECTOR_FUND_FLOW:
            # 获取板块资金流数据
            plugin = self._plugins.get(adapter.plugin_id)
            if plugin and hasattr(plugin, 'get_sector_fund_flow_data'):
                return plugin.get_sector_fund_flow_data(
                    symbol=original_query.symbol,
                    **original_query.extra_params
                )
            else:
                self.logger.warning(f"插件 {adapter.plugin_id} 不支持板块资金流数据")
                return pd.DataFrame()
        elif original_query.data_type == DataType.INDIVIDUAL_FUND_FLOW:
            # 获取个股资金流数据
            plugin = self._plugins.get(adapter.plugin_id)
            if plugin and hasattr(plugin, 'get_individual_fund_flow_data'):
                return plugin.get_individual_fund_flow_data(
                    symbol=original_query.symbol,
                    **original_query.extra_params
                )
            else:
                self.logger.warning(f"插件 {adapter.plugin_id} 不支持个股资金流数据")
                return pd.DataFrame()
        elif original_query.data_type == DataType.MAIN_FUND_FLOW:
            # 获取主力资金流数据
            plugin = self._plugins.get(adapter.plugin_id)
            if plugin and hasattr(plugin, 'get_main_fund_flow_data'):
                return plugin.get_main_fund_flow_data(
                    symbol=original_query.symbol,
                    **original_query.extra_params
                )
            else:
                self.logger.warning(f"插件 {adapter.plugin_id} 不支持主力资金流数据")
                return pd.DataFrame()
        else:
            # 其他数据类型，直接调用插件接口
            plugin = self._plugins.get(adapter.plugin_id)
            if plugin:
                if hasattr(plugin, 'fetch_data'):
                    return plugin.fetch_data(
                        original_query.symbol,
                        original_query.data_type.value,
                        **original_query.extra_params
                    )

        return pd.DataFrame()

    def transform_data(self, raw_data: pd.DataFrame, query: StandardQuery) -> pd.DataFrame:
        """
        Stage 3: 增强的数据标准化 (集成智能字段映射引擎)

        Args:
            raw_data: 原始数据
            query: 查询对象

        Returns:
            pd.DataFrame: 标准化数据
        """
        if raw_data is None or raw_data.empty:
            return pd.DataFrame()

        try:
            self.logger.info(f"开始数据标准化，数据类型: {query.data_type}, 原始字段: {list(raw_data.columns)}")

            # 1. 应用智能字段映射（如果可用）
            if self.field_mapping_engine:
                mapped_data = self.field_mapping_engine.map_fields(raw_data, query.data_type)
            else:
                # 使用基础映射
                mapped_data = raw_data

            # 2. 数据类型转换
            standardized_data = self._standardize_data_types(mapped_data, query.data_type)

            # 3. 数据验证
            if self.field_mapping_engine and not self.field_mapping_engine.validate_mapping_result(standardized_data, query.data_type):
                self.logger.warning(f"数据映射验证失败: {query.data_type}")
                # 降级到基础映射
                standardized_data = self._apply_basic_mapping(raw_data, query)

            # 4. 应用数据质量检查（集成现有功能）
            quality_score = self._calculate_quality_score(standardized_data, query.data_type)
            if 'data_quality_score' not in standardized_data.columns:
                standardized_data['data_quality_score'] = quality_score

            # 5. 数据清洗
            standardized_data = self._clean_data(standardized_data)

            # 6. 最终验证
            standardized_data = self._validate_data(standardized_data, query.data_type)

            self.logger.info(f"数据标准化完成，最终字段: {list(standardized_data.columns)}")
            return standardized_data

        except Exception as e:
            self.logger.error(f"数据标准化失败: {e}")
            # 降级到基础映射
            return self._apply_basic_mapping(raw_data, query)

    def transform_asset_list_data(self, raw_data: pd.DataFrame,
                                  data_source: str = None) -> pd.DataFrame:
        """
        标准化资产列表数据（新增方法 - 真实数据处理）

        功能：
        1. 统一字段名称（不同插件字段名不同）
        2. 数据类型转换和验证
        3. symbol标准化（添加市场后缀）
        4. market推断（从symbol或代码前缀）
        5. 数据清洗和去重

        Args:
            raw_data: 插件返回的原始资产列表DataFrame
            data_source: 数据源名称（用于记录）

        Returns:
            pd.DataFrame: 标准化后的资产列表

        示例：
            >>> raw_df = plugin.get_asset_list()
            >>> standardized_df = pipeline.transform_asset_list_data(raw_df, "eastmoney")
        """
        try:
            if raw_data is None or raw_data.empty:
                return pd.DataFrame()

            self.logger.info(f"开始标准化资产列表: {len(raw_data)} 条记录，数据源: {data_source}")
            self.logger.debug(f"原始字段: {list(raw_data.columns)}")

            # 1. 字段映射（统一不同插件的字段名）
            field_mapping = {
                # 基本字段
                'code': 'symbol',
                'stock_code': 'symbol',
                'ts_code': 'symbol',
                'symbol_code': 'symbol',
                'stock_name': 'name',
                'sec_name': 'name',
                'stock_market': 'market',
                'exchange': 'market',
                'exchange_code': 'market',

                # 分类字段
                'industry_name': 'industry',
                'industryname': 'industry',
                'sector_name': 'sector',
                'sectorname': 'sector',
                'industry_code': 'industry_code',

                # 上市信息
                'list_date': 'listing_date',
                'listdate': 'listing_date',
                'delist_date': 'delisting_date',
                'delistdate': 'delisting_date',
                'status': 'listing_status',
                'list_status': 'listing_status',

                # 股本信息
                'total_capital': 'total_shares',
                'totalcapital': 'total_shares',
                'float_capital': 'circulating_shares',
                'floatcapital': 'circulating_shares',
            }

            # 应用字段映射
            mapped_data = raw_data.rename(columns=field_mapping)

            # 2. 确保必需字段存在
            if 'symbol' not in mapped_data.columns:
                if 'code' in raw_data.columns:
                    mapped_data['symbol'] = raw_data['code']
                else:
                    self.logger.error("缺少symbol/code字段")
                    return pd.DataFrame()

            if 'name' not in mapped_data.columns:
                mapped_data['name'] = None

            # 3. 标准化symbol格式（添加市场后缀）
            def standardize_symbol(symbol):
                """标准化symbol格式：000001 -> 000001.SZ"""
                if not symbol or pd.isna(symbol):
                    return None

                symbol = str(symbol).strip()

                # 已有后缀，直接返回
                if '.' in symbol:
                    return symbol.upper()

                # 根据代码前缀添加后缀
                if symbol.startswith('6'):
                    return f"{symbol}.SH"
                elif symbol.startswith(('0', '3')):
                    return f"{symbol}.SZ"
                elif symbol.startswith(('4', '8', '9')):
                    return f"{symbol}.BJ"
                else:
                    return symbol

            mapped_data['symbol'] = mapped_data['symbol'].apply(standardize_symbol)

            # 4. 向量化推断market字段
            symbols = mapped_data['symbol'].astype(str)
            result_market = pd.Series('unknown', index=mapped_data.index)

            # 保留已有有效market
            if 'market' in mapped_data.columns:
                existing_valid = mapped_data['market'].notna() & (mapped_data['market'] != '') & (mapped_data['market'] != 'unknown')
                result_market[existing_valid] = mapped_data.loc[existing_valid, 'market']

            # 后缀推断
            unknown_mask = result_market == 'unknown'
            result_market[unknown_mask & symbols.str.endswith('.SH')] = 'SH'
            unknown_mask = result_market == 'unknown'
            result_market[unknown_mask & symbols.str.endswith('.SZ')] = 'SZ'
            unknown_mask = result_market == 'unknown'
            result_market[unknown_mask & symbols.str.endswith('.BJ')] = 'BSE'

            # 前缀推断
            unknown_mask = result_market == 'unknown'
            if unknown_mask.any():
                codes = symbols[unknown_mask].str.split('.').str[0]
                first_char = codes.str[0]
                result_market[unknown_mask & (first_char == '6')] = 'SH'
                result_market[unknown_mask & first_char.isin(['0', '3'])] = 'SZ'
                result_market[unknown_mask & first_char.isin(['4', '8', '9'])] = 'BSE'

            mapped_data['market'] = result_market

            # 5. 补全可选字段（删除了不使用的name_en, full_name, short_name字段）
            optional_fields = {
                'asset_type': 'stock_a',
                'exchange': None,
                'sector': None,
                'industry': None,
                'industry_code': None,
                'listing_date': None,
                'delisting_date': None,
                'listing_status': 'active',
                'total_shares': None,
                'circulating_shares': None,
                'currency': 'CNY',
            }

            for field, default_value in optional_fields.items():
                if field not in mapped_data.columns:
                    mapped_data[field] = default_value

            # 6. 数据类型转换
            # 数值字段
            numeric_fields = ['total_shares', 'circulating_shares']
            for field in numeric_fields:
                if field in mapped_data.columns:
                    mapped_data[field] = pd.to_numeric(
                        mapped_data[field],
                        errors='coerce'
                    )

            # 日期字段
            date_fields = ['listing_date', 'delisting_date']
            for field in date_fields:
                if field in mapped_data.columns:
                    mapped_data[field] = pd.to_datetime(
                        mapped_data[field],
                        errors='coerce'
                    )

            # 7. 数据验证和清洗
            # 移除无效记录（symbol或name为空）
            before_count = len(mapped_data)
            mapped_data = mapped_data[
                mapped_data['symbol'].notna() &
                (mapped_data['symbol'] != '') &
                (mapped_data['symbol'] != 'None')
            ]
            after_count = len(mapped_data)

            if before_count > after_count:
                self.logger.warning(
                    f"移除了 {before_count - after_count} 条无效记录（symbol为空）"
                )

            # 8. 去重（按symbol）
            before_count = len(mapped_data)
            mapped_data = mapped_data.drop_duplicates(subset=['symbol'], keep='last')
            after_count = len(mapped_data)

            if before_count > after_count:
                self.logger.warning(
                    f"移除了 {before_count - after_count} 条重复记录"
                )

            # 9. 添加元数据管理字段
            from datetime import datetime
            mapped_data['primary_data_source'] = data_source if data_source else 'unknown'
            mapped_data['last_verified'] = datetime.now()

            self.logger.info(f"资产列表标准化完成: {len(mapped_data)} 条有效记录")
            self.logger.debug(f"标准化后字段: {list(mapped_data.columns)}")

            return mapped_data

        except Exception as e:
            self.logger.error(f"资产列表数据标准化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        # 替换空值
        for null_val in self.null_values:
            data = data.replace(null_val, pd.NA)

        # 删除完全空的行
        data = data.dropna(how='all')

        return data

    def _apply_basic_mapping(self, raw_data: pd.DataFrame, query: StandardQuery) -> pd.DataFrame:
        """
        应用基础字段映射（降级方案）

        Args:
            raw_data: 原始数据
            query: 查询对象

        Returns:
            基础映射后的数据
        """
        try:
            # 获取基础字段映射
            field_mapping = self.field_mappings.get(query.data_type, {})

            # 应用字段映射
            standardized_data = raw_data.copy()
            if field_mapping:
                standardized_data = standardized_data.rename(columns=field_mapping)

            # 数据清洗
            standardized_data = self._clean_data(standardized_data)

            # 数据类型转换
            standardized_data = self._convert_data_types(standardized_data, query.data_type)

            # 数据验证
            standardized_data = self._validate_data(standardized_data, query.data_type)

            return standardized_data

        except Exception as e:
            self.logger.error(f"基础映射失败: {e}")
            return raw_data

    def _standardize_data_types(self, data: pd.DataFrame, data_type: DataType) -> pd.DataFrame:
        """
        标准化数据类型（增强版本）

        Args:
            data: 映射后的数据
            data_type: 数据类型

        Returns:
            类型标准化后的数据
        """
        standardized_data = data.copy()

        try:
            if data_type == DataType.HISTORICAL_KLINE:
                # K线数据类型转换
                numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
                for col in numeric_columns:
                    if col in standardized_data.columns:
                        standardized_data[col] = pd.to_numeric(standardized_data[col], errors='coerce')

                # 处理时间列
                if 'datetime' in standardized_data.columns:
                    standardized_data['datetime'] = pd.to_datetime(standardized_data['datetime'], errors='coerce')
                    if not isinstance(standardized_data.index, pd.DatetimeIndex):
                        standardized_data.set_index('datetime', inplace=True)

            elif data_type == DataType.REAL_TIME_QUOTE:
                # 实时数据类型转换
                numeric_columns = ['current_price', 'bid_price', 'ask_price', 'volume', 'turnover', 'change', 'change_percent']
                for col in numeric_columns:
                    if col in standardized_data.columns:
                        standardized_data[col] = pd.to_numeric(standardized_data[col], errors='coerce')

            elif data_type == DataType.FINANCIAL_STATEMENT:
                # 财务报表数据类型转换
                numeric_columns = [
                    'total_assets', 'total_liabilities', 'shareholders_equity',
                    'operating_revenue', 'net_profit', 'eps', 'operating_cash_flow',
                    'roe', 'roa', 'gross_profit_margin', 'net_profit_margin',
                    'current_ratio', 'debt_to_equity', 'debt_to_assets'
                ]
                for col in numeric_columns:
                    if col in standardized_data.columns:
                        standardized_data[col] = pd.to_numeric(standardized_data[col], errors='coerce')

                # 处理日期列
                if 'report_date' in standardized_data.columns:
                    standardized_data['report_date'] = pd.to_datetime(standardized_data['report_date'], errors='coerce')

            elif data_type == DataType.MACRO_ECONOMIC:
                # 宏观经济数据类型转换
                numeric_columns = ['value', 'mom_change', 'yoy_change', 'qoq_change']
                for col in numeric_columns:
                    if col in standardized_data.columns:
                        standardized_data[col] = pd.to_numeric(standardized_data[col], errors='coerce')

                # 处理日期列
                if 'data_date' in standardized_data.columns:
                    standardized_data['data_date'] = pd.to_datetime(standardized_data['data_date'], errors='coerce')

            return standardized_data

        except Exception as e:
            self.logger.error(f"数据类型标准化失败: {e}")
        return data

    def _calculate_quality_score(self, data: pd.DataFrame, data_type: DataType) -> float:
        """
        计算数据质量评分

        Args:
            data: 数据
            data_type: 数据类型

        Returns:
            质量评分 (0-1)
        """
        try:
            if data.empty:
                return 0.0

            # 基础质量指标
            total_cells = data.shape[0] * data.shape[1]
            null_cells = data.isnull().sum().sum()
            completeness = 1 - (null_cells / total_cells) if total_cells > 0 else 0

            # 数据类型一致性检查
            consistency_score = 1.0
            required_fields = []
            if self.field_mapping_engine:
                required_fields = self.field_mapping_engine._get_required_fields(data_type)

            for field in required_fields:
                if field in data.columns:
                    # 检查数值字段的有效性
                    if field in ['open', 'high', 'low', 'close', 'volume', 'value']:
                        try:
                            numeric_data = pd.to_numeric(data[field], errors='coerce')
                            valid_ratio = numeric_data.notna().sum() / len(data)
                            consistency_score *= valid_ratio
                        except Exception:
                            consistency_score *= 0.5
                else:
                    consistency_score *= 0.8  # 缺少必需字段

            # 综合评分
            quality_score = (completeness * 0.6 + consistency_score * 0.4)
            return min(max(quality_score, 0.0), 1.0)

        except Exception as e:
            self.logger.error(f"质量评分计算失败: {e}")
            return 0.5  # 默认中等质量

    def _convert_data_types(self, data: pd.DataFrame, data_type: DataType) -> pd.DataFrame:
        """转换数据类型"""
        if data_type == DataType.HISTORICAL_KLINE:
            # K线数据类型转换
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')

            # 处理时间列
            if 'datetime' in data.columns:
                data['datetime'] = pd.to_datetime(data['datetime'], errors='coerce')
                if not isinstance(data.index, pd.DatetimeIndex):
                    data.set_index('datetime', inplace=True)

        elif data_type == DataType.REAL_TIME_QUOTE:
            # 实时数据类型转换
            numeric_columns = ['current_price', 'bid_price', 'ask_price', 'volume', 'turnover', 'change', 'change_percent']
            for col in numeric_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')

        return data

    def _validate_data(self, data: pd.DataFrame, data_type: DataType) -> pd.DataFrame:
        """验证数据完整性"""
        if data_type == DataType.HISTORICAL_KLINE:
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                self.logger.warning(f"K线数据缺少必要列: {missing_columns}")

        return data

    def _generate_cache_key(self, query: StandardQuery) -> str:
        """生成缓存键"""
        key_parts = [
            query.symbol,
            query.asset_type.value,
            query.data_type.value,
            query.period,
            query.start_date or "",
            query.end_date or "",
            str(query.extra_params)
        ]
        return "|".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[StandardData]:
        """从缓存获取数据"""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < self._cache_ttl:
                return data
            else:
                del self._cache[cache_key]
        return None

    def _set_to_cache(self, cache_key: str, data: StandardData) -> None:
        """设置缓存"""
        self._cache[cache_key] = (data, datetime.now())

    def _build_metadata(self, query: StandardQuery, raw_data: pd.DataFrame,
                        failover_result: Optional[FailoverResult]) -> Dict[str, Any]:
        """构建元数据"""
        metadata = {
            'query_time': datetime.now().isoformat(),
            'data_count': len(raw_data) if raw_data is not None else 0,
            'asset_type': query.asset_type.value,
            'data_type': query.data_type.value,
            'period': query.period
        }

        if failover_result:
            metadata['failover'] = {
                'success': failover_result.success,
                'attempts': failover_result.attempts,
                'failed_sources': failover_result.failed_sources,
                'successful_source': failover_result.successful_source,
                'total_time_ms': failover_result.total_time_ms
            }

        return metadata

    def _update_stats(self, processing_time_ms: float) -> None:
        """更新统计信息"""
        total_requests = self._stats["total_requests"]
        current_avg = self._stats["avg_processing_time"]

        self._stats["avg_processing_time"] = (
            (current_avg * (total_requests - 1) + processing_time_ms) / total_requests
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            'registered_plugins': len(self._plugins),
            'active_adapters': len(self._adapters),
            'cache_size': len(self._cache),
            'cache_hit_rate': self._stats["cache_hits"] / max(self._stats["total_requests"], 1)
        }

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self.logger.info("TET数据管道缓存已清空")

    def health_check_all_sources(self) -> Dict[str, HealthCheckResult]:
        """检查所有数据源的健康状态"""
        results = {}

        for plugin_id, adapter in self._adapters.items():
            try:
                results[plugin_id] = adapter.health_check()
            except Exception as e:
                results[plugin_id] = HealthCheckResult(
                    is_healthy=False,
                    status_code=500,
                    message=f"健康检查异常: {str(e)}",
                    response_time_ms=0.0,
                    last_check_time=datetime.now()
                )

        return results

    async def process_async(self, query: StandardQuery) -> StandardData:
        """异步处理数据请求"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.process, query)

    def cleanup(self) -> None:
        """清理资源"""
        # 断开所有插件连接
        for adapter in self._adapters.values():
            try:
                adapter.disconnect()
            except Exception as e:
                self.logger.error(f"断开插件连接失败: {e}")

        # 关闭线程池
        self._executor.shutdown(wait=True)

        # 清空缓存
        self.clear_cache()

        self.logger.info("TET数据管道已清理完成")


class HistoryDataStrategy:
    """历史数据加载策略"""

    async def get_data(self, code: str, freq: str, start_date=None, end_date=None):
        """获取历史数据"""
        logger.debug(
            f"Loading historical data for {code} from {start_date} to {end_date}")
        # 实际实现应该调用相应的历史数据服务
        # 这里为示例实现
        try:
            # 模拟异步加载
            await asyncio.sleep(0.1)
            return {'type': 'historical', 'code': code, 'freq': freq, 'data': []}
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return None


class RealtimeDataStrategy:
    """实时数据加载策略"""

    async def get_data(self, code: str, freq: str, start_date=None, end_date=None):
        """获取实时数据"""
        logger.debug(f"Loading realtime data for {code}")
        # 实际实现应该调用实时行情服务
        # 这里为示例实现
        try:
            # 模拟异步加载
            await asyncio.sleep(0.2)
            return {'type': 'realtime', 'code': code, 'freq': freq, 'data': []}
        except Exception as e:
            logger.error(f"Error loading realtime data: {e}")
            return None
