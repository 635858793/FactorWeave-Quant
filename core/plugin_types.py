"""
插件类型定义模块

定义FactorWeave-Quant 系统中支持的所有插件类型和相关枚举。
本模块扩展了原有的插件类型支持，新增数据源插件类型，支持多种资产类型的数据源插件。

作者: FactorWeave-Quant 开发团队  
版本: 1.0.0
日期: 2024
"""

from enum import Enum, auto
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 扩展后的插件类型枚举

class PluginType(Enum):
    """
    插件类型枚举

    定义FactorWeave-Quant 系统支持的所有插件类型，包括原有类型和新增的数据源插件类型。
    """
    # 现有插件类型（保持向下兼容）
    INDICATOR = "indicator"              # 技术指标插件
    SENTIMENT = "sentiment"              # 情绪分析插件
    STRATEGY = "strategy"                # 策略插件
    ANALYSIS = "analysis"                # 分析插件
    UI_COMPONENT = "ui_component"        # UI组件插件
    EXPORT = "export"                    # 导出插件
    NOTIFICATION = "notification"        # 通知插件
    CHART_TOOL = "chart_tool"            # 图表工具插件

    # 新增：数据源插件类型
    DATA_SOURCE = "data_source"          # 通用数据源插件
    DATA_SOURCE_STOCK = "data_source_stock"      # 股票数据源插件
    DATA_SOURCE_FUTURES = "data_source_futures"  # 期货数据源插件
    DATA_SOURCE_CRYPTO = "data_source_crypto"    # 数字货币数据源插件
    DATA_SOURCE_FOREX = "data_source_forex"      # 外汇数据源插件
    DATA_SOURCE_BOND = "data_source_bond"        # 债券数据源插件
    DATA_SOURCE_COMMODITY = "data_source_commodity"  # 商品数据源插件
    DATA_SOURCE_CUSTOM = "data_source_custom"    # 自定义数据源插件
    DATA_SOURCE_WIND = "data_source_wind"        # Wind万得数据源插件

class AssetType(Enum):
    """
    资产类型枚举

    定义系统支持的金融资产类型，用于数据源插件的分类和路由。
    """
    # ✅ 简化：移除通用STOCK类型，统一使用具体的股票类型
    # STOCK = "stock"                        # 已移除：通用股票类型
    
    # 股票类型（具体化）
    STOCK_A = "stock_a"                      # A股（默认股票类型）
    STOCK_B = "stock_b"                      # B股
    STOCK_H = "stock_h"                      # H股
    STOCK_US = "stock_us"                    # 美股
    STOCK_HK = "stock_hk"                    # 港股
    
    # 其他资产类型
    FUTURES = "futures"                      # 期货
    CRYPTO = "crypto"                        # 数字货币
    FOREX = "forex"                          # 外汇
    BOND = "bond"                            # 债券
    COMMODITY = "commodity"                  # 商品
    INDEX = "index"                          # 指数
    FUND = "fund"                            # 基金
    OPTION = "option"                        # 期权
    WARRANT = "warrant"                      # 权证

    # 扩展：板块相关资产类型
    SECTOR = "sector"                        # 板块
    INDUSTRY_SECTOR = "industry_sector"      # 行业板块
    CONCEPT_SECTOR = "concept_sector"        # 概念板块
    STYLE_SECTOR = "style_sector"            # 风格板块
    THEME_SECTOR = "theme_sector"            # 主题板块

    # 扩展：宏观经济数据类型
    MACRO = "macro"                          # 宏观经济数据

class DataType(Enum):
    """
    数据类型枚举

    定义系统支持的数据类型，用于数据源插件的数据分类。
    """
    REAL_TIME_QUOTE = "real_time_quote"      # 实时行情
    HISTORICAL_KLINE = "historical_kline"    # 历史K线
    MARKET_DEPTH = "market_depth"            # 盘口深度
    TRADE_TICK = "trade_tick"                # 逐笔成交
    TICK_DATA = "tick_data"                  # Tick数据
    ORDER_BOOK = "order_book"                # 委托账本
    LEVEL2_DATA = "level2_data"              # Level2行情数据
    FUNDAMENTAL = "fundamental"              # 基本面数据
    NEWS = "news"                            # 新闻数据
    ANNOUNCEMENT = "announcement"            # 公告数据
    ASSET_LIST = "asset_list"                # 资产列表

    # 扩展：资金流相关数据类型
    FUND_FLOW = "fund_flow"                  # 资金流数据
    SECTOR_FUND_FLOW = "sector_fund_flow"    # 板块资金流
    INDIVIDUAL_FUND_FLOW = "individual_fund_flow"  # 个股资金流
    MAIN_FUND_FLOW = "main_fund_flow"        # 主力资金流

    # 扩展：板块相关数据类型
    SECTOR_DATA = "sector_data"              # 板块数据
    SECTOR_ROTATION = "sector_rotation"      # 板块轮动
    CONCEPT_DATA = "concept_data"            # 概念板块数据
    INDUSTRY_DATA = "industry_data"          # 行业板块数据

    # 扩展：技术分析数据类型
    TECHNICAL_INDICATORS = "technical_indicators"  # 技术指标
    PATTERN_RECOGNITION = "pattern_recognition"    # 形态识别
    SENTIMENT_DATA = "sentiment_data"        # 情绪数据

    # 扩展：实时数据类型
    REAL_TIME_FUND_FLOW = "real_time_fund_flow"    # 实时资金流
    REAL_TIME_SECTOR = "real_time_sector"    # 实时板块数据
    INTRADAY_DATA = "intraday_data"          # 分时数据

    # Stage 3 新增：财务和宏观经济数据类型
    FINANCIAL_STATEMENT = "financial_statement"    # 财务报表
    MACRO_ECONOMIC = "macro_economic"              # 宏观经济数据

    # Stage 4 新增：量化系统完整支持
    STOCK_BASIC_INFO = "stock_basic_info"          # 股票基本信息
    OPTION_DATA = "option_data"                    # 期权数据
    FUTURES_DATA = "futures_data"                  # 期货数据
    BOND_DATA = "bond_data"                        # 债券数据
    INDEX_DATA = "index_data"                      # 指数数据
    FUND_DATA = "fund_data"                        # 基金数据
    RISK_METRICS = "risk_metrics"                  # 风险指标
    EVENT_DATA = "event_data"                      # 事件数据
    FACTOR_DATA = "factor_data"                    # 因子数据

class DataSourceProvider(Enum):
    """
    数据源提供商枚举

    标识数据源的提供商，用于插件分类和识别。
    """
    # 现有数据源提供商
    FACTORWEAVE = "factorweave"
    AKSHARE = "akshare"
    EASTMONEY = "eastmoney"
    SINA = "sina"
    TONGHUASHUN = "tonghuashun"

    # 期货数据提供商
    CTP = "ctp"                          # 综合交易平台
    WENHUA = "wenhua"                    # 文华财经
    MYSTEEL = "mysteel"                  # 我的钢铁网

    # 数字货币数据提供商
    BINANCE = "binance"                  # 币安
    COINBASE = "coinbase"                # Coinbase
    HUOBI = "huobi"                      # 火币
    OKX = "okx"                          # OKX交易所

    # 外汇数据提供商
    OANDA = "oanda"                      # OANDA
    FXCM = "fxcm"                        # FXCM

    # 其他数据提供商
    BLOOMBERG = "bloomberg"              # 彭博
    REUTERS = "reuters"                  # 路透
    WIND = "wind"                        # 万得
    CUSTOM = "custom"                    # 自定义

class PluginCategory(Enum):
    """
    插件分类枚举

    用于插件的功能分类和组织，便于用户查找和管理。
    """
    CORE = "core"                        # 核心插件
    COMMUNITY = "community"              # 社区插件
    COMMERCIAL = "commercial"            # 商业插件
    EXPERIMENTAL = "experimental"        # 实验性插件
    DATA = "data"                        # 数据相关插件
    ANALYSIS = "analysis"                # 分析相关插件
    TRADING = "trading"                  # 交易相关插件
    UTILITY = "utility"                  # 工具类插件
    THIRD_PARTY = "third_party"          # 第三方插件

class PluginPriority(Enum):
    """
    插件优先级枚举

    定义插件的加载和执行优先级。
    """
    CRITICAL = 1                         # 关键优先级
    HIGH = 2                             # 高优先级
    NORMAL = 3                           # 普通优先级
    LOW = 4                              # 低优先级
    BACKGROUND = 5                       # 后台优先级

@dataclass
class PluginTypeInfo:
    """
    插件类型信息

    描述特定插件类型的详细信息和约束。
    """
    plugin_type: PluginType
    category: PluginCategory
    description: str
    required_interfaces: List[str]
    optional_interfaces: List[str]
    default_priority: PluginPriority
    config_schema: Optional[Dict[str, Any]] = None
    supported_asset_types: Optional[List[AssetType]] = None

# 插件类型配置映射表
PLUGIN_TYPE_CONFIGS = {
    PluginType.INDICATOR: PluginTypeInfo(
        plugin_type=PluginType.INDICATOR,
        category=PluginCategory.ANALYSIS,
        description="技术指标计算插件",
        required_interfaces=["calculate"],
        optional_interfaces=["validate_params", "get_display_info"],
        default_priority=PluginPriority.NORMAL
    ),

    PluginType.SENTIMENT: PluginTypeInfo(
        plugin_type=PluginType.SENTIMENT,
        category=PluginCategory.ANALYSIS,
        description="市场情绪分析插件",
        required_interfaces=["analyze_sentiment"],
        optional_interfaces=["get_sentiment_indicators"],
        default_priority=PluginPriority.NORMAL
    ),

    PluginType.STRATEGY: PluginTypeInfo(
        plugin_type=PluginType.STRATEGY,
        category=PluginCategory.TRADING,
        description="交易策略插件",
        required_interfaces=["generate_signals"],
        optional_interfaces=["backtest", "optimize_params"],
        default_priority=PluginPriority.HIGH
    ),

    PluginType.DATA_SOURCE: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE,
        category=PluginCategory.DATA,
        description="通用数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.HIGH,
        supported_asset_types=list(AssetType)
    ),

    PluginType.DATA_SOURCE_STOCK: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_STOCK,
        category=PluginCategory.DATA,
        description="股票数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.HIGH,
        supported_asset_types=[
            AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H,
            AssetType.STOCK_US, AssetType.STOCK_HK,
            AssetType.INDEX, AssetType.FUND
        ]
    ),

    PluginType.DATA_SOURCE_FUTURES: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_FUTURES,
        category=PluginCategory.DATA,
        description="期货数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.HIGH,
        supported_asset_types=[AssetType.FUTURES, AssetType.COMMODITY, AssetType.OPTION]
    ),

    PluginType.DATA_SOURCE_CRYPTO: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_CRYPTO,
        category=PluginCategory.DATA,
        description="数字货币数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.NORMAL,
        supported_asset_types=[AssetType.CRYPTO]
    ),

    PluginType.DATA_SOURCE_FOREX: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_FOREX,
        category=PluginCategory.DATA,
        description="外汇数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.NORMAL,
        supported_asset_types=[AssetType.FOREX]
    ),

    PluginType.DATA_SOURCE_BOND: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_BOND,
        category=PluginCategory.DATA,
        description="债券数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.LOW,
        supported_asset_types=[AssetType.BOND]
    ),

    PluginType.DATA_SOURCE_COMMODITY: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_COMMODITY,
        category=PluginCategory.DATA,
        description="商品数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.NORMAL,
        supported_asset_types=[AssetType.COMMODITY, AssetType.FUTURES]
    ),

    PluginType.DATA_SOURCE_CUSTOM: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_CUSTOM,
        category=PluginCategory.DATA,
        description="自定义数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.NORMAL,
        supported_asset_types=list(AssetType)
    ),

    PluginType.DATA_SOURCE_WIND: PluginTypeInfo(
        plugin_type=PluginType.DATA_SOURCE_WIND,
        category=PluginCategory.DATA,
        description="Wind万得数据源插件",
        required_interfaces=[
            "get_plugin_info", "initialize", "fetch_data",
            "get_real_time_data", "health_check"
        ],
        optional_interfaces=["get_config_schema", "validate_config"],
        default_priority=PluginPriority.HIGH,
        supported_asset_types=[
            AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H,
            AssetType.INDEX, AssetType.FUND, AssetType.BOND,
            AssetType.FUTURES, AssetType.OPTION
        ]
    )
}

def get_plugin_type_info(plugin_type: PluginType) -> Optional[PluginTypeInfo]:
    """
    获取插件类型信息

    Args:
        plugin_type: 插件类型

    Returns:
        PluginTypeInfo: 插件类型信息，如果类型不存在则返回None
    """
    return PLUGIN_TYPE_CONFIGS.get(plugin_type)

def get_data_source_plugin_types() -> List[PluginType]:
    """
    获取所有数据源插件类型

    Returns:
        List[PluginType]: 数据源插件类型列表
    """
    return [
        PluginType.DATA_SOURCE,
        PluginType.DATA_SOURCE_STOCK,
        PluginType.DATA_SOURCE_FUTURES,
        PluginType.DATA_SOURCE_CRYPTO,
        PluginType.DATA_SOURCE_FOREX,
        PluginType.DATA_SOURCE_BOND,
        PluginType.DATA_SOURCE_COMMODITY,
        PluginType.DATA_SOURCE_CUSTOM,
        PluginType.DATA_SOURCE_WIND
    ]

def is_data_source_plugin(plugin_type: PluginType) -> bool:
    """
    判断是否为数据源插件类型

    Args:
        plugin_type: 插件类型

    Returns:
        bool: 是否为数据源插件
    """
    return plugin_type in get_data_source_plugin_types()

def get_supported_asset_types(plugin_type: PluginType) -> List[AssetType]:
    """
    获取插件类型支持的资产类型

    Args:
        plugin_type: 插件类型

    Returns:
        List[AssetType]: 支持的资产类型列表
    """
    type_info = get_plugin_type_info(plugin_type)
    if type_info and type_info.supported_asset_types:
        return type_info.supported_asset_types
    return []

def validate_plugin_type_compatibility(plugin_type: PluginType,
                                       asset_types: List[AssetType]) -> bool:
    """
    验证插件类型与资产类型的兼容性

    Args:
        plugin_type: 插件类型
        asset_types: 资产类型列表

    Returns:
        bool: 是否兼容
    """
    if not is_data_source_plugin(plugin_type):
        return True  # 非数据源插件不需要验证资产类型

    supported_types = get_supported_asset_types(plugin_type)
    if not supported_types:
        return True  # 如果没有限制，则兼容所有类型

    # 检查是否有交集
    return bool(set(asset_types) & set(supported_types))

def get_default_provider_for_asset_type(asset_type: AssetType) -> DataSourceProvider:
    """
    获取资产类型的默认数据源提供商

    Args:
        asset_type: 资产类型

    Returns:
        DataSourceProvider: 默认数据源提供商
    """
    provider_mapping = {
        AssetType.STOCK_A: DataSourceProvider.FACTORWEAVE,
        AssetType.STOCK_B: DataSourceProvider.EASTMONEY,
        AssetType.STOCK_H: DataSourceProvider.EASTMONEY,
        AssetType.STOCK_US: DataSourceProvider.CUSTOM,
        AssetType.STOCK_HK: DataSourceProvider.EASTMONEY,
        AssetType.INDEX: DataSourceProvider.FACTORWEAVE,
        AssetType.FUND: DataSourceProvider.AKSHARE,
        AssetType.FUTURES: DataSourceProvider.CTP,
        AssetType.COMMODITY: DataSourceProvider.MYSTEEL,
        AssetType.CRYPTO: DataSourceProvider.BINANCE,
        AssetType.FOREX: DataSourceProvider.OANDA,
        AssetType.BOND: DataSourceProvider.WIND,
        AssetType.OPTION: DataSourceProvider.CTP,
        AssetType.WARRANT: DataSourceProvider.EASTMONEY,
        AssetType.SECTOR: DataSourceProvider.EASTMONEY,
        AssetType.INDUSTRY_SECTOR: DataSourceProvider.EASTMONEY,
        AssetType.CONCEPT_SECTOR: DataSourceProvider.EASTMONEY,
        AssetType.STYLE_SECTOR: DataSourceProvider.FACTORWEAVE,
        AssetType.THEME_SECTOR: DataSourceProvider.EASTMONEY,
        AssetType.MACRO: DataSourceProvider.WIND
    }

    return provider_mapping.get(asset_type, DataSourceProvider.CUSTOM)

# 导出的公共接口
__all__ = [
    'PluginType',
    'AssetType',
    'DataType',
    'DataSourceProvider',
    'PluginCategory',
    'PluginPriority',
    'PluginTypeInfo',
    'PLUGIN_TYPE_CONFIGS',
    'get_plugin_type_info',
    'get_data_source_plugin_types',
    'is_data_source_plugin',
    'get_supported_asset_types',
    'validate_plugin_type_compatibility',
    'get_default_provider_for_asset_type'
]
