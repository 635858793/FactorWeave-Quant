from loguru import logger
"""
DuckDB动态表管理器

提供DuckDB数据表的动态管理，包括：
- 按插件名动态创建表
- 表结构版本管理
- 索引自动创建
- 分区策略实施
- 表结构迁移

作者: FactorWeave-Quant团队
版本: 1.0
"""

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import json
import re
from datetime import datetime, date

from .duckdb_manager import DuckDBConnectionManager, get_connection_manager
from ..plugin_types import DataType
from .unified_table_name_generator import UnifiedTableNameGenerator, generate_table_name
from ..plugin_types import AssetType



class TableType(Enum):
    """表类型枚举"""
    # 基础数据类型
    STOCK_BASIC_INFO = "stock_basic_info"
    KLINE_DATA = "kline_data"
    FINANCIAL_STATEMENT = "financial_statement"
    MACRO_ECONOMIC = "macro_economic"
    REAL_TIME_QUOTE = "real_time_quote"
    MARKET_DEPTH = "market_depth"
    TRADE_TICK = "trade_tick"
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    FUND_FLOW = "fund_flow"
    TECHNICAL_INDICATOR = "technical_indicator"

    # 风险管理相关（对应现有功能）
    RISK_METRICS = "risk_metrics"

    # 扩展数据类型（有对应功能支持）
    INDEX_DATA = "index_data"
    EVENT_DATA = "event_data"
    ASSET_LIST = "asset_list"
    SECTOR_DATA = "sector_data"
    PATTERN_RECOGNITION = "pattern_recognition"

    # 板块资金流相关表
    SECTOR_FUND_FLOW_DAILY = "sector_fund_flow_daily"
    SECTOR_FUND_FLOW_INTRADAY = "sector_fund_flow_intraday"

    # 回测结果相关表
    BACKTEST_RESULTS = "backtest_results"  # 回测结果存储


@dataclass
class TableSchema:
    """表结构定义"""
    table_type: TableType
    columns: Dict[str, str]  # 列名 -> 数据类型
    primary_key: List[str]
    indexes: List[Dict[str, Any]]  # 索引定义
    partitions: Optional[Dict[str, Any]] = None  # 分区定义
    constraints: Optional[List[str]] = None  # 约束条件
    version: str = "1.0"


class TableSchemaRegistry:
    """表结构注册表"""

    def __init__(self):
        """初始化表结构注册表"""
        self._schemas: Dict[TableType, TableSchema] = {}
        self._initialize_default_schemas()

    def _initialize_default_schemas(self):
        """初始化默认表结构"""

        # 股票基础信息表
        self._schemas[TableType.STOCK_BASIC_INFO] = TableSchema(
            table_type=TableType.STOCK_BASIC_INFO,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'name': 'VARCHAR NOT NULL',
                'market': 'VARCHAR NOT NULL',
                'exchange': 'VARCHAR',
                'industry_l1': 'VARCHAR',
                'industry_l2': 'VARCHAR',
                'industry_l3': 'VARCHAR',
                'concept_plates': 'VARCHAR[]',
                'list_date': 'DATE',
                'delist_date': 'DATE',
                'total_shares': 'BIGINT',
                'float_shares': 'BIGINT',
                'market_cap': 'DECIMAL(20,2)',
                'float_market_cap': 'DECIMAL(20,2)',
                'pe_ratio': 'DECIMAL(10,4)',
                'pb_ratio': 'DECIMAL(10,4)',
                'ps_ratio': 'DECIMAL(10,4)',
                'ev_ebitda': 'DECIMAL(10,4)',
                'beta': 'DECIMAL(10,6)',
                'ma5': 'DECIMAL(10,4)',
                'ma10': 'DECIMAL(10,4)',
                'ma20': 'DECIMAL(10,4)',
                'ma60': 'DECIMAL(10,4)',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol'],
            indexes=[
                {'name': 'idx_market', 'columns': ['market']},
                {'name': 'idx_industry', 'columns': ['industry_l1', 'industry_l2']},
                {'name': 'idx_list_date', 'columns': ['list_date']},
                {'name': 'idx_market_cap', 'columns': ['market_cap']},
                {'name': 'idx_data_source', 'columns': ['data_source']},
                {'name': 'idx_updated_at', 'columns': ['updated_at']}
            ]
        )

        # K线数据表
        self._schemas[TableType.KLINE_DATA] = TableSchema(
            table_type=TableType.KLINE_DATA,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'frequency': 'VARCHAR NOT NULL DEFAULT \'1d\'',
                'open': 'DECIMAL(10,4) NOT NULL',
                'high': 'DECIMAL(10,4) NOT NULL',
                'low': 'DECIMAL(10,4) NOT NULL',
                'close': 'DECIMAL(10,4) NOT NULL',
                'volume': 'BIGINT NOT NULL',
                'amount': 'DECIMAL(20,2)',
                'adj_close': 'DECIMAL(10,4)',
                'adj_factor': 'DECIMAL(10,6)',
                'adj_type': 'VARCHAR(10)',    # 复权类型 (qfq/hfq/none)
                'adj_source': 'VARCHAR(20)',  # 复权数据来源 (plugin/calculated)
                'vwap': 'DECIMAL(10,4)',
                'bid_price': 'DECIMAL(10,4)',
                'ask_price': 'DECIMAL(10,4)',
                'bid_volume': 'BIGINT',
                'ask_volume': 'BIGINT',
                'rsi_14': 'DECIMAL(10,4)',
                'macd_dif': 'DECIMAL(10,4)',
                'macd_dea': 'DECIMAL(10,4)',
                'macd_histogram': 'DECIMAL(10,4)',
                'kdj_k': 'DECIMAL(10,4)',
                'kdj_d': 'DECIMAL(10,4)',
                'kdj_j': 'DECIMAL(10,4)',
                'bollinger_upper': 'DECIMAL(10,4)',
                'bollinger_middle': 'DECIMAL(10,4)',
                'bollinger_lower': 'DECIMAL(10,4)',
                'turnover_rate': 'DECIMAL(10,4)',
                'net_inflow_large': 'DECIMAL(20,2)',
                'net_inflow_medium': 'DECIMAL(20,2)',
                'net_inflow_small': 'DECIMAL(20,2)',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime', 'frequency'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_frequency', 'columns': ['frequency']},
                {'name': 'idx_symbol_datetime', 'columns': ['symbol', 'datetime']},
                {'name': 'idx_symbol_frequency', 'columns': ['symbol', 'frequency']},
                {'name': 'idx_volume', 'columns': ['volume']},
                {'name': 'idx_amount', 'columns': ['amount']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'datetime',
                'interval': 'MONTH'
            }
        )

        # 财务报表表
        self._schemas[TableType.FINANCIAL_STATEMENT] = TableSchema(
            table_type=TableType.FINANCIAL_STATEMENT,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'report_date': 'DATE NOT NULL',
                'report_type': 'VARCHAR NOT NULL',
                'report_period': 'VARCHAR',
                'fiscal_year': 'INTEGER',
                # 资产负债表 - 资产
                'total_assets': 'DECIMAL(20,2)',
                'current_assets': 'DECIMAL(20,2)',
                'non_current_assets': 'DECIMAL(20,2)',
                'cash_and_equivalents': 'DECIMAL(20,2)',
                'short_term_investments': 'DECIMAL(20,2)',
                'accounts_receivable': 'DECIMAL(20,2)',
                'inventory': 'DECIMAL(20,2)',
                'prepaid_expenses': 'DECIMAL(20,2)',
                'fixed_assets': 'DECIMAL(20,2)',
                'intangible_assets': 'DECIMAL(20,2)',
                'goodwill': 'DECIMAL(20,2)',
                # 资产负债表 - 负债
                'total_liabilities': 'DECIMAL(20,2)',
                'current_liabilities': 'DECIMAL(20,2)',
                'non_current_liabilities': 'DECIMAL(20,2)',
                'accounts_payable': 'DECIMAL(20,2)',
                'short_term_debt': 'DECIMAL(20,2)',
                'long_term_debt': 'DECIMAL(20,2)',
                'accrued_expenses': 'DECIMAL(20,2)',
                # 资产负债表 - 股东权益
                'shareholders_equity': 'DECIMAL(20,2)',
                'paid_in_capital': 'DECIMAL(20,2)',
                'retained_earnings': 'DECIMAL(20,2)',
                'accumulated_other_comprehensive_income': 'DECIMAL(20,2)',
                # 利润表
                'operating_revenue': 'DECIMAL(20,2)',
                'operating_costs': 'DECIMAL(20,2)',
                'gross_profit': 'DECIMAL(20,2)',
                'operating_expenses': 'DECIMAL(20,2)',
                'selling_expenses': 'DECIMAL(20,2)',
                'admin_expenses': 'DECIMAL(20,2)',
                'rd_expenses': 'DECIMAL(20,2)',
                'financial_expenses': 'DECIMAL(20,2)',
                'operating_profit': 'DECIMAL(20,2)',
                'non_operating_income': 'DECIMAL(20,2)',
                'non_operating_expenses': 'DECIMAL(20,2)',
                'profit_before_tax': 'DECIMAL(20,2)',
                'income_tax': 'DECIMAL(20,2)',
                'net_profit': 'DECIMAL(20,2)',
                'net_profit_attributable_to_parent': 'DECIMAL(20,2)',
                # 每股指标
                'eps': 'DECIMAL(10,4)',
                'diluted_eps': 'DECIMAL(10,4)',
                'book_value_per_share': 'DECIMAL(10,4)',
                # 现金流量表
                'operating_cash_flow': 'DECIMAL(20,2)',
                'investing_cash_flow': 'DECIMAL(20,2)',
                'financing_cash_flow': 'DECIMAL(20,2)',
                'net_cash_flow': 'DECIMAL(20,2)',
                'free_cash_flow': 'DECIMAL(20,2)',
                # 经营活动现金流明细
                'cash_from_operations': 'DECIMAL(20,2)',
                'cash_paid_for_goods': 'DECIMAL(20,2)',
                'cash_paid_to_employees': 'DECIMAL(20,2)',
                'cash_paid_for_taxes': 'DECIMAL(20,2)',
                # 盈利能力比率
                'roe': 'DECIMAL(10,4)',
                'roa': 'DECIMAL(10,4)',
                'roic': 'DECIMAL(10,4)',
                'gross_profit_margin': 'DECIMAL(10,4)',
                'operating_profit_margin': 'DECIMAL(10,4)',
                'net_profit_margin': 'DECIMAL(10,4)',
                # 偿债能力比率
                'current_ratio': 'DECIMAL(10,4)',
                'quick_ratio': 'DECIMAL(10,4)',
                'debt_to_equity': 'DECIMAL(10,4)',
                'debt_to_assets': 'DECIMAL(10,4)',
                'interest_coverage': 'DECIMAL(10,4)',
                # 营运能力比率
                'asset_turnover': 'DECIMAL(10,4)',
                'inventory_turnover': 'DECIMAL(10,4)',
                'receivables_turnover': 'DECIMAL(10,4)',
                # 成长能力比率
                'revenue_growth': 'DECIMAL(10,4)',
                'profit_growth': 'DECIMAL(10,4)',
                'asset_growth': 'DECIMAL(10,4)',
                # 元数据
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'report_date', 'report_type'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_report_date', 'columns': ['report_date']},
                {'name': 'idx_report_type', 'columns': ['report_type']},
                {'name': 'idx_symbol_date', 'columns': ['symbol', 'report_date']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ]
        )

        # 宏观经济数据表
        self._schemas[TableType.MACRO_ECONOMIC] = TableSchema(
            table_type=TableType.MACRO_ECONOMIC,
            columns={
                'indicator_code': 'VARCHAR NOT NULL',
                'data_date': 'DATE NOT NULL',
                'value': 'DECIMAL(20,6) NOT NULL',
                'indicator_name': 'VARCHAR NOT NULL',
                'frequency': 'VARCHAR NOT NULL',
                'unit': 'VARCHAR',
                'category': 'VARCHAR',
                'subcategory': 'VARCHAR',
                'country': 'VARCHAR DEFAULT \'CN\'',
                'region': 'VARCHAR',
                'seasonally_adjusted': 'BOOLEAN DEFAULT FALSE',
                'data_source': 'VARCHAR NOT NULL',
                'source_code': 'VARCHAR',
                'release_date': 'DATE',
                'revision_date': 'DATE',
                'plugin_specific_data': 'JSON',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['indicator_code', 'data_date'],
            indexes=[
                {'name': 'idx_indicator_code', 'columns': ['indicator_code']},
                {'name': 'idx_data_date', 'columns': ['data_date']},
                {'name': 'idx_category', 'columns': ['category', 'subcategory']},
                {'name': 'idx_country', 'columns': ['country', 'region']},
                {'name': 'idx_frequency', 'columns': ['frequency']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ]
        )

        # 实时行情表
        self._schemas[TableType.REAL_TIME_QUOTE] = TableSchema(
            table_type=TableType.REAL_TIME_QUOTE,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'price': 'DECIMAL(10,4) NOT NULL',
                'volume': 'BIGINT NOT NULL',
                'amount': 'DECIMAL(20,2)',
                'change': 'DECIMAL(10,4)',
                'change_percent': 'DECIMAL(10,4)',
                'open': 'DECIMAL(10,4)',
                'high': 'DECIMAL(10,4)',
                'low': 'DECIMAL(10,4)',
                'prev_close': 'DECIMAL(10,4)',
                'bid_price': 'DECIMAL(10,4)',
                'ask_price': 'DECIMAL(10,4)',
                'bid_volume': 'BIGINT',
                'ask_volume': 'BIGINT',
                'total_bid_volume': 'BIGINT',
                'total_ask_volume': 'BIGINT',
                'turnover_rate': 'DECIMAL(10,4)',
                'market_status': 'VARCHAR',
                'average_price': 'DECIMAL(10,4)',
                'price_limit_up': 'DECIMAL(10,4)',
                'price_limit_down': 'DECIMAL(10,4)',
                'suspension_status': 'VARCHAR',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_price', 'columns': ['price']},
                {'name': 'idx_volume', 'columns': ['volume']},
                {'name': 'idx_market_status', 'columns': ['market_status']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ]
        )

        # 市场深度表
        self._schemas[TableType.MARKET_DEPTH] = TableSchema(
            table_type=TableType.MARKET_DEPTH,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'bid_price_1': 'DECIMAL(10,4)',
                'bid_volume_1': 'BIGINT',
                'bid_price_2': 'DECIMAL(10,4)',
                'bid_volume_2': 'BIGINT',
                'bid_price_3': 'DECIMAL(10,4)',
                'bid_volume_3': 'BIGINT',
                'bid_price_4': 'DECIMAL(10,4)',
                'bid_volume_4': 'BIGINT',
                'bid_price_5': 'DECIMAL(10,4)',
                'bid_volume_5': 'BIGINT',
                'ask_price_1': 'DECIMAL(10,4)',
                'ask_volume_1': 'BIGINT',
                'ask_price_2': 'DECIMAL(10,4)',
                'ask_volume_2': 'BIGINT',
                'ask_price_3': 'DECIMAL(10,4)',
                'ask_volume_3': 'BIGINT',
                'ask_price_4': 'DECIMAL(10,4)',
                'ask_volume_4': 'BIGINT',
                'ask_price_5': 'DECIMAL(10,4)',
                'ask_volume_5': 'BIGINT',
                'total_bid_volume': 'BIGINT',
                'total_ask_volume': 'BIGINT',
                'weighted_bid_price': 'DECIMAL(10,4)',
                'weighted_ask_price': 'DECIMAL(10,4)',
                'spread': 'DECIMAL(10,4)',
                'mid_price': 'DECIMAL(10,4)',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_bid_price_1', 'columns': ['bid_price_1']},
                {'name': 'idx_ask_price_1', 'columns': ['ask_price_1']},
                {'name': 'idx_spread', 'columns': ['spread']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ]
        )

        # 交易Tick表
        self._schemas[TableType.TRADE_TICK] = TableSchema(
            table_type=TableType.TRADE_TICK,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'price': 'DECIMAL(10,4) NOT NULL',
                'volume': 'BIGINT NOT NULL',
                'amount': 'DECIMAL(20,2) NOT NULL',
                'tick_direction': 'VARCHAR',  # 'buy', 'sell', 'neutral'
                'order_type': 'VARCHAR',      # 'market', 'limit'
                'trade_type': 'VARCHAR',      # 'normal', 'block', 'special'
                'buyer_order_id': 'VARCHAR',
                'seller_order_id': 'VARCHAR',
                'seq_number': 'BIGINT',
                'channel': 'VARCHAR',
                'function_code': 'VARCHAR',
                'bid_price': 'DECIMAL(10,4)',
                'ask_price': 'DECIMAL(10,4)',
                'bid_volume': 'BIGINT',
                'ask_volume': 'BIGINT',
                'cumulative_volume': 'BIGINT',
                'cumulative_amount': 'DECIMAL(20,2)',
                'trade_flag': 'VARCHAR',
                'cancel_flag': 'BOOLEAN DEFAULT FALSE',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime', 'seq_number'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_symbol_datetime', 'columns': ['symbol', 'datetime']},
                {'name': 'idx_price', 'columns': ['price']},
                {'name': 'idx_volume', 'columns': ['volume']},
                {'name': 'idx_tick_direction', 'columns': ['tick_direction']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'datetime',
                'interval': 'DAY'
            }
        )

        # 新闻表
        self._schemas[TableType.NEWS] = TableSchema(
            table_type=TableType.NEWS,
            columns={
                'news_id': 'VARCHAR NOT NULL',
                'title': 'VARCHAR NOT NULL',
                'content': 'TEXT',
                'summary': 'TEXT',
                'publish_time': 'TIMESTAMP NOT NULL',
                'source': 'VARCHAR NOT NULL',
                'author': 'VARCHAR',
                'category': 'VARCHAR',
                'subcategory': 'VARCHAR',
                'tags': 'VARCHAR[]',
                'related_symbols': 'VARCHAR[]',
                'related_industries': 'VARCHAR[]',
                'sentiment_score': 'DECIMAL(3,2)',    # -1.0 to 1.0
                'impact_score': 'DECIMAL(3,2)',       # 0.0 to 1.0
                'language': 'VARCHAR DEFAULT \'zh\'',
                'url': 'VARCHAR',
                'image_urls': 'VARCHAR[]',
                'read_count': 'INTEGER DEFAULT 0',
                'like_count': 'INTEGER DEFAULT 0',
                'comment_count': 'INTEGER DEFAULT 0',
                'keywords': 'VARCHAR[]',
                'is_verified': 'BOOLEAN DEFAULT FALSE',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['news_id'],
            indexes=[
                {'name': 'idx_publish_time', 'columns': ['publish_time']},
                {'name': 'idx_source', 'columns': ['source']},
                {'name': 'idx_category', 'columns': ['category', 'subcategory']},
                {'name': 'idx_related_symbols', 'columns': ['related_symbols']},
                {'name': 'idx_sentiment_score', 'columns': ['sentiment_score']},
                {'name': 'idx_impact_score', 'columns': ['impact_score']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'publish_time',
                'interval': 'MONTH'
            }
        )

        # 公告表
        self._schemas[TableType.ANNOUNCEMENT] = TableSchema(
            table_type=TableType.ANNOUNCEMENT,
            columns={
                'announcement_id': 'VARCHAR NOT NULL',
                'symbol': 'VARCHAR NOT NULL',
                'title': 'VARCHAR NOT NULL',
                'content': 'TEXT NOT NULL',
                'summary': 'TEXT',
                'announcement_type': 'VARCHAR NOT NULL',  # 业绩预告、重大事项、股权变动等
                'importance_level': 'VARCHAR NOT NULL',   # 高、中、低
                'publish_time': 'TIMESTAMP NOT NULL',
                'effective_date': 'DATE',
                'disclosure_date': 'DATE',
                'update_time': 'TIMESTAMP',
                'announcement_source': 'VARCHAR',         # 交易所、公司官网等
                'filing_type': 'VARCHAR',                 # 定期报告、临时公告等
                'related_announcements': 'VARCHAR[]',     # 相关公告ID
                'impact_type': 'VARCHAR',                 # 利好、利空、中性
                'impact_description': 'TEXT',
                'keywords': 'VARCHAR[]',
                'attachments': 'JSON',                    # 附件信息
                'regulation_compliance': 'BOOLEAN DEFAULT TRUE',
                'is_correction': 'BOOLEAN DEFAULT FALSE',
                'correction_reason': 'TEXT',
                'market_reaction_score': 'DECIMAL(3,2)',
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['announcement_id'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_publish_time', 'columns': ['publish_time']},
                {'name': 'idx_announcement_type', 'columns': ['announcement_type']},
                {'name': 'idx_importance_level', 'columns': ['importance_level']},
                {'name': 'idx_symbol_publish_time', 'columns': ['symbol', 'publish_time']},
                {'name': 'idx_impact_type', 'columns': ['impact_type']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'publish_time',
                'interval': 'MONTH'
            }
        )

        # 资金流表
        self._schemas[TableType.FUND_FLOW] = TableSchema(
            table_type=TableType.FUND_FLOW,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'period': 'VARCHAR NOT NULL',              # 'minute', 'daily'
                'main_inflow': 'DECIMAL(20,2)',           # 主力流入
                'main_outflow': 'DECIMAL(20,2)',          # 主力流出
                'main_net_inflow': 'DECIMAL(20,2)',       # 主力净流入
                'retail_inflow': 'DECIMAL(20,2)',         # 散户流入
                'retail_outflow': 'DECIMAL(20,2)',        # 散户流出
                'retail_net_inflow': 'DECIMAL(20,2)',     # 散户净流入
                'large_order_inflow': 'DECIMAL(20,2)',    # 大单流入
                'large_order_outflow': 'DECIMAL(20,2)',   # 大单流出
                'large_order_net_inflow': 'DECIMAL(20,2)',  # 大单净流入
                'medium_order_inflow': 'DECIMAL(20,2)',   # 中单流入
                'medium_order_outflow': 'DECIMAL(20,2)',  # 中单流出
                'medium_order_net_inflow': 'DECIMAL(20,2)',  # 中单净流入
                'small_order_inflow': 'DECIMAL(20,2)',    # 小单流入
                'small_order_outflow': 'DECIMAL(20,2)',   # 小单流出
                'small_order_net_inflow': 'DECIMAL(20,2)',  # 小单净流入
                'super_large_inflow': 'DECIMAL(20,2)',    # 超大单流入
                'super_large_outflow': 'DECIMAL(20,2)',   # 超大单流出
                'super_large_net_inflow': 'DECIMAL(20,2)',  # 超大单净流入
                'total_inflow': 'DECIMAL(20,2)',          # 总流入
                'total_outflow': 'DECIMAL(20,2)',         # 总流出
                'net_inflow': 'DECIMAL(20,2)',            # 净流入
                'inflow_ratio': 'DECIMAL(5,2)',           # 流入占比
                'main_participation_ratio': 'DECIMAL(5,2)',  # 主力参与度
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime', 'period'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_period', 'columns': ['period']},
                {'name': 'idx_symbol_datetime', 'columns': ['symbol', 'datetime']},
                {'name': 'idx_main_net_inflow', 'columns': ['main_net_inflow']},
                {'name': 'idx_net_inflow', 'columns': ['net_inflow']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'datetime',
                'interval': 'MONTH'
            }
        )

        # 技术指标表
        self._schemas[TableType.TECHNICAL_INDICATOR] = TableSchema(
            table_type=TableType.TECHNICAL_INDICATOR,
            columns={
                'symbol': 'VARCHAR NOT NULL',
                'datetime': 'TIMESTAMP NOT NULL',
                'period': 'VARCHAR NOT NULL',              # 'minute', 'daily', 'weekly'
                'indicator_name': 'VARCHAR NOT NULL',       # MA, RSI, MACD, KDJ等
                'indicator_params': 'JSON',                # 指标参数配置
                'value_1': 'DECIMAL(15,6)',               # 主要值（如MA值、RSI值）
                'value_2': 'DECIMAL(15,6)',               # 辅助值（如MACD的DIF）
                'value_3': 'DECIMAL(15,6)',               # 辅助值（如MACD的DEA）
                'value_4': 'DECIMAL(15,6)',               # 辅助值（如MACD的柱状图）
                'value_5': 'DECIMAL(15,6)',               # 辅助值（预留）
                'signal': 'VARCHAR',                       # 信号类型：买入、卖出、持有
                'signal_strength': 'DECIMAL(3,2)',        # 信号强度 0-1
                'calculation_method': 'VARCHAR',           # 计算方法
                'data_window_size': 'INTEGER',             # 计算窗口大小
                'is_divergence': 'BOOLEAN DEFAULT FALSE',  # 是否存在背离
                'divergence_type': 'VARCHAR',              # 背离类型
                'trend_direction': 'VARCHAR',              # 趋势方向：上升、下降、横盘
                'support_level': 'DECIMAL(10,4)',         # 支撑位
                'resistance_level': 'DECIMAL(10,4)',      # 阻力位
                'confidence_level': 'DECIMAL(3,2)',       # 可信度
                'calculation_timestamp': 'TIMESTAMP',      # 计算时间戳
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime', 'period', 'indicator_name'],
            indexes=[
                {'name': 'idx_symbol', 'columns': ['symbol']},
                {'name': 'idx_datetime', 'columns': ['datetime']},
                {'name': 'idx_indicator_name', 'columns': ['indicator_name']},
                {'name': 'idx_period', 'columns': ['period']},
                {'name': 'idx_symbol_indicator', 'columns': ['symbol', 'indicator_name']},
                {'name': 'idx_signal', 'columns': ['signal']},
                {'name': 'idx_signal_strength', 'columns': ['signal_strength']},
                {'name': 'idx_data_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'datetime',
                'interval': 'MONTH'
            }
        )

        # 其余重要表类型的简化定义（优化版本）
        # 风险指标表
        self._schemas[TableType.RISK_METRICS] = TableSchema(
            table_type=TableType.RISK_METRICS,
            columns={
                'symbol': 'VARCHAR NOT NULL', 'datetime': 'TIMESTAMP NOT NULL',
                'var_1d': 'DECIMAL(10,6)', 'var_5d': 'DECIMAL(10,6)', 'cvar': 'DECIMAL(10,6)',
                'beta': 'DECIMAL(10,6)', 'alpha': 'DECIMAL(10,6)', 'sharpe_ratio': 'DECIMAL(10,6)',
                'volatility': 'DECIMAL(10,6)', 'max_drawdown': 'DECIMAL(10,6)',
                'correlation_matrix': 'JSON', 'risk_factors': 'JSON',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime'],
            indexes=[{'name': 'idx_var_1d', 'columns': ['var_1d']}, {'name': 'idx_beta', 'columns': ['beta']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 指数数据表
        self._schemas[TableType.INDEX_DATA] = TableSchema(
            table_type=TableType.INDEX_DATA,
            columns={
                'symbol': 'VARCHAR NOT NULL', 'datetime': 'TIMESTAMP NOT NULL',
                'index_value': 'DECIMAL(15,4) NOT NULL', 'change': 'DECIMAL(10,4)', 'change_percent': 'DECIMAL(10,4)',
                'constituents': 'JSON', 'weights': 'JSON', 'divisor': 'DECIMAL(20,6)',
                'market_cap': 'DECIMAL(25,2)', 'free_float_cap': 'DECIMAL(25,2)',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol', 'datetime'],
            indexes=[{'name': 'idx_index_value', 'columns': ['index_value']}, {'name': 'idx_change_percent', 'columns': ['change_percent']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 事件数据表
        self._schemas[TableType.EVENT_DATA] = TableSchema(
            table_type=TableType.EVENT_DATA,
            columns={
                'symbol': 'VARCHAR NOT NULL', 'event_id': 'VARCHAR NOT NULL', 'event_type': 'VARCHAR NOT NULL',
                'ex_date': 'DATE', 'record_date': 'DATE', 'announcement_date': 'DATE',
                'amount': 'DECIMAL(10,4)', 'ratio': 'DECIMAL(10,6)', 'description': 'TEXT',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['event_id'],
            indexes=[{'name': 'idx_symbol', 'columns': ['symbol']}, {'name': 'idx_event_type', 'columns': ['event_type']}, {'name': 'idx_ex_date', 'columns': ['ex_date']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 资产列表表
        self._schemas[TableType.ASSET_LIST] = TableSchema(
            table_type=TableType.ASSET_LIST,
            columns={
                'symbol': 'VARCHAR NOT NULL', 'name': 'VARCHAR NOT NULL', 'asset_type': 'VARCHAR NOT NULL',
                'exchange': 'VARCHAR', 'listing_status': 'VARCHAR', 'sector': 'VARCHAR', 'industry': 'VARCHAR',
                'currency': 'VARCHAR', 'country': 'VARCHAR', 'listing_date': 'DATE', 'delisting_date': 'DATE',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['symbol'],
            indexes=[{'name': 'idx_asset_type', 'columns': ['asset_type']}, {'name': 'idx_exchange', 'columns': ['exchange']}, {'name': 'idx_sector', 'columns': ['sector']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 板块数据表
        self._schemas[TableType.SECTOR_DATA] = TableSchema(
            table_type=TableType.SECTOR_DATA,
            columns={
                'sector_code': 'VARCHAR NOT NULL', 'datetime': 'TIMESTAMP NOT NULL',
                'sector_name': 'VARCHAR NOT NULL', 'constituents': 'JSON', 'weights': 'JSON',
                'sector_value': 'DECIMAL(15,4)', 'change_percent': 'DECIMAL(10,4)',
                'market_cap': 'DECIMAL(25,2)', 'turnover_rate': 'DECIMAL(10,4)',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['sector_code', 'datetime'],
            indexes=[{'name': 'idx_sector_name', 'columns': ['sector_name']}, {'name': 'idx_change_percent', 'columns': ['change_percent']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 形态识别表
        self._schemas[TableType.PATTERN_RECOGNITION] = TableSchema(
            table_type=TableType.PATTERN_RECOGNITION,
            columns={
                'symbol': 'VARCHAR NOT NULL', 'pattern_id': 'VARCHAR NOT NULL', 'datetime': 'TIMESTAMP NOT NULL',
                'pattern_type': 'VARCHAR NOT NULL', 'pattern_score': 'DECIMAL(5,4)', 'confidence': 'DECIMAL(5,4)',
                'start_date': 'DATE', 'end_date': 'DATE', 'target_price': 'DECIMAL(10,4)',
                'success_rate': 'DECIMAL(5,4)', 'description': 'TEXT',
                'plugin_specific_data': 'JSON', 'data_source': 'VARCHAR NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'data_quality_score': 'DECIMAL(3,2)'
            },
            primary_key=['pattern_id'],
            indexes=[{'name': 'idx_symbol', 'columns': ['symbol']}, {'name': 'idx_pattern_type', 'columns': ['pattern_type']}, {'name': 'idx_pattern_score', 'columns': ['pattern_score']}, {'name': 'idx_data_source', 'columns': ['data_source']}]
        )

        # 板块资金流日度数据表
        self._schemas[TableType.SECTOR_FUND_FLOW_DAILY] = TableSchema(
            table_type=TableType.SECTOR_FUND_FLOW_DAILY,
            columns={
                'sector_id': 'VARCHAR(20) NOT NULL',              # 板块ID，对应现有FUND_FLOW表的symbol字段
                'sector_name': 'VARCHAR(100) NOT NULL',           # 板块名称，例如"房地产"、"医药生物"
                'sector_code': 'VARCHAR(20)',                     # 板块代码，例如"BK0001"
                'trade_date': 'DATE NOT NULL',                    # 交易日期，分区键

                # 复用现有FUND_FLOW表的标准资金流字段
                'main_inflow': 'DECIMAL(20,2)',                   # 主力流入金额（万元）
                'main_outflow': 'DECIMAL(20,2)',                  # 主力流出金额（万元）
                'main_net_inflow': 'DECIMAL(20,2)',               # 主力净流入=main_inflow-main_outflow
                'retail_inflow': 'DECIMAL(20,2)',                 # 散户流入金额（万元）
                'retail_outflow': 'DECIMAL(20,2)',                # 散户流出金额（万元）
                'retail_net_inflow': 'DECIMAL(20,2)',             # 散户净流入=retail_inflow-retail_outflow
                'large_order_inflow': 'DECIMAL(20,2)',            # 大单流入
                'large_order_outflow': 'DECIMAL(20,2)',           # 大单流出
                'large_order_net_inflow': 'DECIMAL(20,2)',        # 大单净流入
                'medium_order_inflow': 'DECIMAL(20,2)',           # 中单流入
                'medium_order_outflow': 'DECIMAL(20,2)',          # 中单流出
                'medium_order_net_inflow': 'DECIMAL(20,2)',       # 中单净流入
                'small_order_inflow': 'DECIMAL(20,2)',            # 小单流入
                'small_order_outflow': 'DECIMAL(20,2)',           # 小单流出
                'small_order_net_inflow': 'DECIMAL(20,2)',        # 小单净流入

                # 板块特有的聚合字段
                'stock_count': 'INTEGER',                         # 板块内股票总数
                'rise_count': 'INTEGER',                          # 上涨股票数量
                'fall_count': 'INTEGER',                          # 下跌股票数量
                'flat_count': 'INTEGER',                          # 平盘股票数量
                'avg_change_pct': 'DECIMAL(8,4)',                 # 板块平均涨跌幅(%)
                'total_turnover': 'DECIMAL(20,2)',                # 板块总成交金额
                'rank_by_amount': 'INTEGER',                      # 按净流入金额排名
                'rank_by_ratio': 'INTEGER',                       # 按流入占比排名

                # 复用现有元数据字段
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR(50) NOT NULL',            # 数据来源："akshare"、"eastmoney"等
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'              # 数据质量评分0.00-1.00
            },
            primary_key=['sector_id', 'trade_date'],
            indexes=[
                {'name': 'idx_sector_daily_date', 'columns': ['trade_date']},
                {'name': 'idx_sector_daily_ranking', 'columns': ['trade_date', 'rank_by_amount']},
                {'name': 'idx_sector_daily_inflow', 'columns': ['trade_date', 'main_net_inflow']},
                {'name': 'idx_sector_daily_sector', 'columns': ['sector_id']},
                {'name': 'idx_sector_daily_source', 'columns': ['data_source']}
            ],
            partitions={
                'type': 'range',
                'column': 'trade_date',
                'interval': 'MONTH'
            }
        )

        # 板块资金流分时数据表
        self._schemas[TableType.SECTOR_FUND_FLOW_INTRADAY] = TableSchema(
            table_type=TableType.SECTOR_FUND_FLOW_INTRADAY,
            columns={
                'sector_id': 'VARCHAR(20) NOT NULL',              # 板块ID
                'trade_date': 'DATE NOT NULL',                    # 交易日期
                'trade_time': 'TIME NOT NULL',                    # 交易时间，分钟级别，例如：09:30:00

                # 累计数据（相对于开盘时间）
                'cumulative_main_inflow': 'DECIMAL(18,2)',        # 开盘至当前时间的累计主力净流入
                'cumulative_retail_inflow': 'DECIMAL(18,2)',      # 开盘至当前时间的累计散户净流入
                'cumulative_turnover': 'DECIMAL(18,2)',           # 开盘至当前时间的累计成交金额

                # 区间数据（相对于前一分钟）
                'interval_main_inflow': 'DECIMAL(18,2)',          # 当前分钟相比前一分钟的主力净流入变化
                'interval_retail_inflow': 'DECIMAL(18,2)',        # 当前分钟相比前一分钟的散户净流入变化
                'interval_turnover': 'DECIMAL(18,2)',             # 当前分钟的成交金额

                # 速度和强度指标
                'main_inflow_speed': 'DECIMAL(12,4)',             # 主力流入速度（万元/分钟）
                'retail_inflow_speed': 'DECIMAL(12,4)',           # 散户流入速度（万元/分钟）
                'active_degree': 'DECIMAL(8,4)',                  # 活跃度指标（0-1之间）
                'volatility_index': 'DECIMAL(8,4)',               # 波动率指数

                # 元数据
                'data_source': 'VARCHAR(50) NOT NULL',
                'update_time': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            },
            primary_key=['sector_id', 'trade_date', 'trade_time'],
            indexes=[
                {'name': 'idx_sector_intraday_lookup', 'columns': ['sector_id', 'trade_date']},
                {'name': 'idx_sector_intraday_time', 'columns': ['trade_date', 'trade_time']},
                {'name': 'idx_sector_intraday_sector', 'columns': ['sector_id']},
                {'name': 'idx_sector_intraday_source', 'columns': ['data_source']}
            ]
        )

        logger.info("默认表结构初始化完成 - 已加载19种完整表结构（新增板块资金流日度和分时表）")

    def get_schema(self, table_type: TableType) -> Optional[TableSchema]:
        """获取表结构"""
        return self._schemas.get(table_type)

    def register_schema(self, schema: TableSchema):
        """注册表结构"""
        self._schemas[schema.table_type] = schema
        logger.info(f"表结构已注册: {schema.table_type}")

    def get_all_schemas(self) -> Dict[TableType, TableSchema]:
        """获取所有表结构"""
        return self._schemas.copy()


class DynamicTableManager:
    """动态表管理器"""

    def __init__(self, connection_manager: Optional[DuckDBConnectionManager] = None):
        """
        初始化动态表管理器

        Args:
            connection_manager: DuckDB连接管理器
        """
        self.connection_manager = connection_manager or get_connection_manager()
        self.schema_registry = TableSchemaRegistry()

        # 表名缓存
        self._table_cache: Dict[str, bool] = {}

        logger.info("动态表管理器初始化完成")

    def generate_table_name(self, table_type: TableType, plugin_name: str,
                            period: Optional[str] = None, market: Optional[str] = None,
                            asset_type: Optional[AssetType] = None) -> str:
        """
        生成动态表名（使用统一表名生成器）

        Args:
            table_type: 表类型
            plugin_name: 插件名称
            period: 数据周期（可选）
            market: 市场代码（可选）
            asset_type: 资产类型（可选）

        Returns:
            标准化表名
        """
        try:
            # 将TableType转换为DataType
            data_type_mapping = {
                # 基础数据类型
                TableType.KLINE_DATA: DataType.HISTORICAL_KLINE,
                TableType.STOCK_BASIC_INFO: DataType.STOCK_BASIC_INFO,
                TableType.FINANCIAL_STATEMENT: DataType.FINANCIAL_STATEMENT,
                TableType.MACRO_ECONOMIC: DataType.MACRO_ECONOMIC,
                TableType.REAL_TIME_QUOTE: DataType.REAL_TIME_QUOTE,
                TableType.MARKET_DEPTH: DataType.MARKET_DEPTH,
                TableType.TRADE_TICK: DataType.TRADE_TICK,
                TableType.NEWS: DataType.NEWS,
                TableType.ANNOUNCEMENT: DataType.ANNOUNCEMENT,
                TableType.FUND_FLOW: DataType.FUND_FLOW,
                TableType.TECHNICAL_INDICATOR: DataType.TECHNICAL_INDICATORS,

                # 风险管理相关
                TableType.RISK_METRICS: DataType.RISK_METRICS,

                # 扩展数据类型
                TableType.INDEX_DATA: DataType.INDEX_DATA,
                TableType.EVENT_DATA: DataType.EVENT_DATA,
                TableType.ASSET_LIST: DataType.ASSET_LIST,
                TableType.SECTOR_DATA: DataType.SECTOR_DATA,
                TableType.PATTERN_RECOGNITION: DataType.PATTERN_RECOGNITION
            }

            # 获取对应的DataType
            data_type = data_type_mapping.get(table_type)
            if not data_type:
                # 如果没有映射，使用表类型值创建临时DataType
                logger.warning(f"未找到TableType {table_type} 的DataType映射，使用默认值")
                # 创建一个临时的DataType对象

                class TempDataType:
                    def __init__(self, value):
                        self.value = value
                data_type = TempDataType(table_type.value)

            # 使用统一表名生成器（使用SIMPLE模式，避免market=all后缀）
            from .unified_table_name_generator import TableNamePattern
            return UnifiedTableNameGenerator.generate(
                data_type=data_type,
                plugin_name=plugin_name,
                period=period,
                market=market,
                asset_type=asset_type,
                pattern=TableNamePattern.SIMPLE  # 使用SIMPLE模式：{data_type}_{plugin_name}_{period}
            )

        except Exception as e:
            logger.error(f"使用统一表名生成器失败: {e}，回退到旧方法")
            # 回退到旧的表名生成方法
            clean_plugin_name = re.sub(r'[^a-zA-Z0-9_]', '_', plugin_name.lower())
            base_name = f"{table_type.value}_{clean_plugin_name}"
            if period:
                clean_period = re.sub(r'[^a-zA-Z0-9_]', '_', period.lower())
                base_name = f"{base_name}_{clean_period}"
            return base_name

    def table_exists(self, database_path: str, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            database_path: 数据库路径
            table_name: 表名

        Returns:
            表是否存在
        """
        cache_key = f"{database_path}:{table_name}"

        # 检查缓存
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        try:
            with self.connection_manager.get_connection(database_path) as conn:
                # 使用duckdb_tables()内置函数，比information_schema更高效
                result = conn.execute(
                    "SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = ?",
                    [table_name]
                ).fetchone()

                exists = result[0] > 0
                self._table_cache[cache_key] = exists
                return exists

        except Exception as e:
            logger.error(f"检查表存在性失败 {table_name}: {e}")
            return False

    def ensure_table_exists(self, database_path: str, table_type: TableType,
                            plugin_name: str, period: Optional[str] = None,
                            custom_schema: Optional[TableSchema] = None) -> str:
        """
        确保表存在，如果不存在则创建

        Args:
            database_path: 数据库路径
            table_type: 表类型
            plugin_name: 插件名称
            period: 数据周期（可选）
            custom_schema: 自定义表结构（可选）

        Returns:
            表名（如果成功）或None（如果失败）
        """
        try:
            # 生成表名
            table_name = self.generate_table_name(table_type, plugin_name, period)

            # 检查表是否已存在
            if self.table_exists(database_path, table_name):
                return table_name

            # 表不存在，创建表
            success = self.create_table(database_path, table_type, plugin_name, period, custom_schema)
            return table_name if success else None

        except Exception as e:
            logger.error(f"确保表存在失败 {table_type} {plugin_name}: {e}")
            return None

    def create_table(self, database_path: str, table_type: TableType,
                     plugin_name: str, period: Optional[str] = None,
                     custom_schema: Optional[TableSchema] = None) -> bool:
        """
        创建表

        Args:
            database_path: 数据库路径
            table_type: 表类型
            plugin_name: 插件名称
            period: 数据周期（可选）
            custom_schema: 自定义表结构（可选）

        Returns:
            创建是否成功
        """
        try:
            # 生成表名
            table_name = self.generate_table_name(table_type, plugin_name, period)

            # 检查表是否已存在
            if self.table_exists(database_path, table_name):
                logger.info(f"表已存在: {table_name}")
                return True

            # 获取表结构
            schema = custom_schema or self.schema_registry.get_schema(table_type)
            if not schema:
                logger.error(f"未找到表结构: {table_type}")
                return False

            # 生成CREATE TABLE语句
            create_sql = self._generate_create_table_sql(table_name, schema)

            # 执行创建表
            with self.connection_manager.get_connection(database_path) as conn:
                conn.execute(create_sql)
                logger.info(f"表创建成功: {table_name}")

                # 创建索引
                self._create_indexes(conn, table_name, schema)

                # 创建分区（如果需要）
                if schema.partitions:
                    self._create_partitions(conn, table_name, schema)

            # 更新缓存
            cache_key = f"{database_path}:{table_name}"
            self._table_cache[cache_key] = True

            return True

        except Exception as e:
            logger.error(f"创建表失败 {table_type} {plugin_name}: {e}")
            return False

    def _generate_create_table_sql(self, table_name: str, schema: TableSchema) -> str:
        """生成CREATE TABLE SQL语句"""
        columns_sql = []

        for column_name, column_type in schema.columns.items():
            columns_sql.append(f"    {column_name} {column_type}")

        # 添加主键约束
        if schema.primary_key:
            pk_columns = ', '.join(schema.primary_key)
            columns_sql.append(f"    PRIMARY KEY ({pk_columns})")

        # 添加其他约束
        if schema.constraints:
            for constraint in schema.constraints:
                columns_sql.append(f"    {constraint}")

        # 修复f-string中的反斜杠问题
        columns_joined = ',\n'.join(columns_sql)
        create_sql = f"""
CREATE TABLE {table_name} (
{columns_joined}
)"""

        return create_sql

    def _create_indexes(self, conn, table_name: str, schema: TableSchema):
        """创建索引"""
        try:
            for index_def in schema.indexes:
                index_name = f"{table_name}_{index_def['name']}"
                columns = ', '.join(index_def['columns'])

                # 检查索引类型
                index_type = index_def.get('type', 'BTREE')
                unique = 'UNIQUE ' if index_def.get('unique', False) else ''

                # DuckDB不支持USING子句，直接创建索引
                index_sql = f"CREATE {unique}INDEX {index_name} ON {table_name} ({columns})"

                conn.execute(index_sql)
                logger.debug(f"索引创建成功: {index_name}")

        except Exception as e:
            logger.error(f"创建索引失败 {table_name}: {e}")

    def _create_partitions(self, conn, table_name: str, schema: TableSchema):
        """创建分区（DuckDB暂不完全支持，预留接口）"""
        try:
            partition_info = schema.partitions
            if partition_info['type'] == 'range':
                # DuckDB的分区功能有限，这里主要是预留接口
                logger.info(f"分区配置已记录: {table_name} - {partition_info}")

        except Exception as e:
            logger.error(f"创建分区失败 {table_name}: {e}")

    def drop_table(self, database_path: str, table_type: TableType,
                   plugin_name: str, period: Optional[str] = None) -> bool:
        """
        删除表

        Args:
            database_path: 数据库路径
            table_type: 表类型
            plugin_name: 插件名称
            period: 数据周期（可选）

        Returns:
            删除是否成功
        """
        try:
            table_name = self.generate_table_name(table_type, plugin_name, period)

            if not self.table_exists(database_path, table_name):
                logger.info(f"表不存在: {table_name}")
                return True

            with self.connection_manager.get_connection(database_path) as conn:
                conn.execute(f"DROP TABLE {table_name}")
                logger.info(f"表删除成功: {table_name}")

            # 更新缓存
            cache_key = f"{database_path}:{table_name}"
            self._table_cache[cache_key] = False

            return True

        except Exception as e:
            logger.error(f"删除表失败 {table_type} {plugin_name}: {e}")
            return False

    def get_table_info(self, database_path: str, table_name: str) -> Optional[Dict[str, Any]]:
        """
        获取表信息

        Args:
            database_path: 数据库路径
            table_name: 表名

        Returns:
            表信息
        """
        try:
            with self.connection_manager.get_connection(database_path) as conn:
                # 获取表结构信息
                columns_info = conn.execute(f"DESCRIBE {table_name}").fetchall()

                # 获取索引信息（DuckDB使用duckdb_indexes系统表）
                try:
                    indexes_info = conn.execute(
                        "SELECT index_name, column_names, is_unique FROM duckdb_indexes() WHERE table_name = ?",
                        [table_name]
                    ).fetchall()
                except Exception:
                    # 如果系统表不可用，返回空列表
                    indexes_info = []

                # 获取表统计信息
                stats = conn.execute(f"SELECT COUNT(*) as row_count FROM {table_name}").fetchone()

                return {
                    'table_name': table_name,
                    'columns': columns_info,
                    'indexes': indexes_info,
                    'row_count': stats[0] if stats else 0,
                    'database_path': database_path
                }

        except Exception as e:
            logger.error(f"获取表信息失败 {table_name}: {e}")
            return None

    def list_tables(self, database_path: str, plugin_name: Optional[str] = None) -> List[str]:
        """
        列出表

        Args:
            database_path: 数据库路径
            plugin_name: 插件名称过滤（可选）

        Returns:
            表名列表
        """
        try:
            with self.connection_manager.get_connection(database_path) as conn:
                if plugin_name:
                    # 过滤特定插件的表
                    clean_plugin_name = re.sub(r'[^a-zA-Z0-9_]', '_', plugin_name.lower())
                    pattern = f"%_{clean_plugin_name}%"

                    # 使用duckdb_tables()更高效
                    result = conn.execute(
                        "SELECT table_name FROM duckdb_tables() WHERE table_name LIKE ?",
                        [pattern]
                    ).fetchall()
                else:
                    # 获取所有表
                    result = conn.execute(
                        "SELECT table_name FROM duckdb_tables()"
                    ).fetchall()

                return [row[0] for row in result]

        except Exception as e:
            logger.error(f"列出表失败: {e}")
            return []

    def migrate_table_schema(self, database_path: str, table_name: str,
                             new_schema: TableSchema) -> bool:
        """
        迁移表结构

        Args:
            database_path: 数据库路径
            table_name: 表名
            new_schema: 新的表结构

        Returns:
            迁移是否成功
        """
        try:
            with self.connection_manager.get_connection(database_path) as conn:
                # 获取当前表结构
                current_columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
                current_column_names = {col[0] for col in current_columns}

                # 比较新旧结构，生成迁移SQL
                migration_sqls = []

                for column_name, column_type in new_schema.columns.items():
                    if column_name not in current_column_names:
                        # 添加新列
                        migration_sqls.append(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

                # 执行迁移
                for sql in migration_sqls:
                    conn.execute(sql)
                    logger.debug(f"执行迁移SQL: {sql}")

                logger.info(f"表结构迁移完成: {table_name}")
                return True

        except Exception as e:
            logger.error(f"表结构迁移失败 {table_name}: {e}")
            return False

    def get_schema(self, table_type: TableType) -> Optional[TableSchema]:
        """
        获取表结构

        Args:
            table_type: 表类型

        Returns:
            表结构对象或None
        """
        return self.schema_registry.get_schema(table_type)

    def clear_table_cache(self):
        """清理表缓存"""
        self._table_cache.clear()
        logger.info("表缓存已清理")

    def get_table_statistics(self, database_path: str) -> Dict[str, Any]:
        """
        获取数据库表统计信息

        Args:
            database_path: 数据库路径

        Returns:
            统计信息
        """
        try:
            with self.connection_manager.get_connection(database_path) as conn:
                # 获取表数量 - 使用duckdb_tables()更高效
                table_count = conn.execute(
                    "SELECT COUNT(*) FROM duckdb_tables()"
                ).fetchone()[0]

                # 获取各类型表的数量
                type_counts = {}
                for table_type in TableType:
                    pattern = f"{table_type.value}_%"
                    count = conn.execute(
                        "SELECT COUNT(*) FROM duckdb_tables() WHERE table_name LIKE ?",
                        [pattern]
                    ).fetchone()[0]
                    type_counts[table_type.value] = count

                # 获取数据库大小信息
                db_size = conn.execute(
                    "SELECT database_size FROM pragma_database_size()"
                ).fetchone()

                return {
                    'database_path': database_path,
                    'total_tables': table_count,
                    'table_type_counts': type_counts,
                    'database_size_bytes': db_size[0] if db_size else 0,
                    'cache_size': len(self._table_cache)
                }

        except Exception as e:
            logger.error(f"获取表统计信息失败: {e}")
            return {
                'database_path': database_path,
                'error': str(e)
            }


# 全局表管理器实例
_table_manager: Optional[DynamicTableManager] = None


def get_table_manager() -> DynamicTableManager:
    """获取全局表管理器实例"""
    global _table_manager

    if _table_manager is None:
        _table_manager = DynamicTableManager()

    return _table_manager
