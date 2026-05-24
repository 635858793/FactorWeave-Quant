"""
增强数据模型定义

基于TET数据标准和行业专业软件（Wind、Bloomberg等）数据结构设计的
多数据源插件统一数据模型。

版本: 1.0
作者: FactorWeave-Quant Team
日期: 2025-01-27
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from enum import Enum
import pandas as pd
import json

# 导入统一的数据质量模型
from .unified_quality_models import (
    DataQuality, QualityDimension, QualityCheckStatus, QualityIssueLevel,
    UnifiedDataQualityMetrics, QualityProfile, get_default_quality_profiles
)

class MarketType(Enum):
    """市场类型"""
    STOCK = "stock"         # 股票市场
    FUTURES = "futures"     # 期货市场
    FOREX = "forex"         # 外汇市场
    CRYPTO = "crypto"       # 数字货币市场
    BOND = "bond"           # 债券市场
    COMMODITY = "commodity"  # 商品市场

class ReportType(Enum):
    """财报类型"""
    ANNUAL = "annual"       # 年报
    SEMI_ANNUAL = "semi_annual"  # 半年报
    QUARTERLY = "quarterly"  # 季报
    MONTHLY = "monthly"     # 月报

@dataclass
class EnhancedStockInfo:
    """
    增强股票基本信息模型

    对标Wind万得、Bloomberg等专业软件的股票基本信息结构
    """
    # 基础标识字段
    symbol: str                              # 股票代码
    name: str                               # 股票名称
    market: str                             # 市场代码 (sh/sz/hk/us等)
    exchange: Optional[str] = None          # 交易所代码

    # 基本面信息 (对标Wind)
    industry_l1: Optional[str] = None       # 一级行业分类
    industry_l2: Optional[str] = None       # 二级行业分类
    industry_l3: Optional[str] = None       # 三级行业分类
    sector: Optional[str] = None            # 板块分类
    concept_plates: List[str] = field(default_factory=list)  # 概念板块

    # 上市信息
    list_date: Optional[date] = None        # 上市日期
    delist_date: Optional[date] = None      # 退市日期
    list_status: Optional[str] = None       # 上市状态

    # 市值信息
    total_shares: Optional[int] = None      # 总股本
    float_shares: Optional[int] = None      # 流通股本
    market_cap: Optional[Decimal] = None    # 总市值
    float_market_cap: Optional[Decimal] = None  # 流通市值

    # 财务指标
    pe_ratio: Optional[Decimal] = None      # 市盈率(TTM)
    pb_ratio: Optional[Decimal] = None      # 市净率
    ps_ratio: Optional[Decimal] = None      # 市销率
    pcf_ratio: Optional[Decimal] = None     # 市现率

    # 估值指标 (对标Bloomberg)
    ev_ebitda: Optional[Decimal] = None     # 企业价值倍数
    roe: Optional[Decimal] = None           # 净资产收益率
    roa: Optional[Decimal] = None           # 总资产收益率
    gross_margin: Optional[Decimal] = None  # 毛利率
    net_margin: Optional[Decimal] = None    # 净利率

    # 风险指标
    beta: Optional[Decimal] = None          # Beta系数
    volatility_30d: Optional[Decimal] = None   # 30日波动率
    volatility_252d: Optional[Decimal] = None  # 年化波动率

    # 技术指标
    ma5: Optional[Decimal] = None           # 5日均线
    ma10: Optional[Decimal] = None          # 10日均线
    ma20: Optional[Decimal] = None          # 20日均线
    ma60: Optional[Decimal] = None          # 60日均线

    # 扩展字段 (插件特有数据)
    plugin_specific_data: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    data_source: str = ""                   # 数据源标识
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_quality_score: Optional[Decimal] = None  # 数据质量评分

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (date, datetime)):
                result[key] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, list):
                result[key] = value
            elif isinstance(value, dict):
                result[key] = value
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedStockInfo':
        """从字典创建实例"""
        # 处理日期字段
        if 'list_date' in data and data['list_date']:
            data['list_date'] = datetime.fromisoformat(data['list_date']).date()
        if 'delist_date' in data and data['delist_date']:
            data['delist_date'] = datetime.fromisoformat(data['delist_date']).date()
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and data['updated_at']:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        # 处理Decimal字段
        decimal_fields = [
            'market_cap', 'float_market_cap', 'pe_ratio', 'pb_ratio', 'ps_ratio',
            'pcf_ratio', 'ev_ebitda', 'roe', 'roa', 'gross_margin', 'net_margin',
            'beta', 'volatility_30d', 'volatility_252d', 'ma5', 'ma10', 'ma20',
            'ma60', 'data_quality_score'
        ]
        for field_name in decimal_fields:
            if field_name in data and data[field_name] is not None:
                data[field_name] = Decimal(str(data[field_name]))

        return cls(**data)

@dataclass
class EnhancedKlineData:
    """
    增强K线数据模型

    对标Wind、Bloomberg等专业软件的K线数据结构，
    包含OHLCV、复权价格、技术指标、资金流向等信息
    """
    # 基础字段
    symbol: str                             # 股票代码
    datetime: datetime                      # 时间戳

    # OHLCV标准字段
    open: Decimal                           # 开盘价
    high: Decimal                           # 最高价
    low: Decimal                            # 最低价
    close: Decimal                          # 收盘价
    volume: int                             # 成交量
    amount: Optional[Decimal] = None        # 成交额

    # 复权价格 (对标Wind)
    adj_close: Optional[Decimal] = None     # 后复权收盘价
    adj_open: Optional[Decimal] = None      # 后复权开盘价
    adj_high: Optional[Decimal] = None      # 后复权最高价
    adj_low: Optional[Decimal] = None       # 后复权最低价
    adj_factor: Optional[Decimal] = None    # 复权因子

    # 市场微观结构 (对标Bloomberg)
    vwap: Optional[Decimal] = None          # 成交量加权平均价
    twap: Optional[Decimal] = None          # 时间加权平均价
    bid_price: Optional[Decimal] = None     # 买一价
    ask_price: Optional[Decimal] = None     # 卖一价
    bid_volume: Optional[int] = None        # 买一量
    ask_volume: Optional[int] = None        # 卖一量
    spread: Optional[Decimal] = None        # 买卖价差

    # 技术指标预计算
    rsi_14: Optional[Decimal] = None        # 14日RSI
    macd_dif: Optional[Decimal] = None      # MACD DIF
    macd_dea: Optional[Decimal] = None      # MACD DEA
    macd_histogram: Optional[Decimal] = None  # MACD柱状图
    kdj_k: Optional[Decimal] = None         # KDJ K值
    kdj_d: Optional[Decimal] = None         # KDJ D值
    kdj_j: Optional[Decimal] = None         # KDJ J值

    # 市场情绪指标
    turnover_rate: Optional[Decimal] = None  # 换手率
    amplitude: Optional[Decimal] = None     # 振幅
    change_pct: Optional[Decimal] = None    # 涨跌幅
    change_amount: Optional[Decimal] = None  # 涨跌额

    # 资金流向 (对标东方财富)
    net_inflow_large: Optional[Decimal] = None   # 大单净流入
    net_inflow_medium: Optional[Decimal] = None  # 中单净流入
    net_inflow_small: Optional[Decimal] = None   # 小单净流入
    net_inflow_main: Optional[Decimal] = None    # 主力净流入

    # 扩展字段
    plugin_specific_data: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    data_source: str = ""                   # 数据源标识
    created_at: datetime = field(default_factory=datetime.now)
    data_quality_score: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, dict):
                result[key] = value
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedKlineData':
        """从字典创建实例"""
        # 处理日期时间字段
        if 'datetime' in data and isinstance(data['datetime'], str):
            data['datetime'] = datetime.fromisoformat(data['datetime'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        # 处理Decimal字段
        decimal_fields = [
            'open', 'high', 'low', 'close', 'amount', 'adj_close', 'adj_open',
            'adj_high', 'adj_low', 'adj_factor', 'vwap', 'twap', 'bid_price',
            'ask_price', 'spread', 'rsi_14', 'macd_dif', 'macd_dea', 'macd_histogram',
            'kdj_k', 'kdj_d', 'kdj_j', 'turnover_rate', 'amplitude', 'change_pct',
            'change_amount', 'net_inflow_large', 'net_inflow_medium', 'net_inflow_small',
            'net_inflow_main', 'data_quality_score'
        ]
        for field_name in decimal_fields:
            if field_name in data and data[field_name] is not None:
                data[field_name] = Decimal(str(data[field_name]))

        return cls(**data)

@dataclass
class DataSourcePlugin:
    """
    数据源插件信息模型
    """
    plugin_name: str                        # 插件唯一标识
    display_name: str                       # 显示名称
    plugin_type: str                        # 插件类型
    version: str                            # 版本号

    # 支持的资产类型和数据类型
    supported_assets: List[str] = field(default_factory=list)
    supported_data_types: List[str] = field(default_factory=list)
    supported_markets: List[str] = field(default_factory=list)

    # 配置信息
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    api_endpoints: Dict[str, str] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)

    # 字段映射
    field_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    # 状态信息
    status: str = "inactive"                # 插件状态
    priority: int = 100                     # 优先级
    is_enabled: bool = True                 # 是否启用

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_sync_at: Optional[datetime] = None  # 最后同步时间

    # 统计信息
    total_requests: int = 0                 # 总请求数
    success_requests: int = 0               # 成功请求数
    error_requests: int = 0                 # 错误请求数
    avg_response_time: Optional[Decimal] = None  # 平均响应时间

@dataclass
class FieldMapping:
    """
    字段映射配置模型
    """
    plugin_name: str                        # 插件名称
    data_type: str                          # 数据类型
    source_field: str                       # 源字段名
    target_field: str                       # 目标标准字段名
    field_type: str                         # 字段类型
    transform_rule: Dict[str, Any] = field(default_factory=dict)  # 转换规则
    validation_rule: Dict[str, Any] = field(default_factory=dict)  # 验证规则
    is_required: bool = False               # 是否必需
    default_value: Optional[str] = None     # 默认值

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

# 兼容性别名 - DataQualityMetrics现在指向UnifiedDataQualityMetrics
DataQualityMetrics = UnifiedDataQualityMetrics

# 工具函数
def generate_table_name(plugin_name: str, data_type: str, period: str = None) -> str:
    """
    生成标准化表名

    Args:
        plugin_name: 插件名称
        data_type: 数据类型
        period: 周期（可选）

    Returns:
        标准化表名
    """
    base_name = f"{data_type}_{plugin_name}"
    if period:
        return f"{base_name}_{period}"
    return base_name

def validate_symbol(symbol: str, market: str) -> bool:
    """
    验证股票代码格式

    Args:
        symbol: 股票代码
        market: 市场代码

    Returns:
        是否有效
    """
    if not symbol or not market:
        return False

    # 基本格式验证
    if market.lower() in ['sh', 'sz']:
        # A股代码验证
        return len(symbol) == 6 and symbol.isdigit()
    elif market.lower() == 'hk':
        # 港股代码验证
        return len(symbol) <= 5 and symbol.isdigit()
    elif market.lower() == 'us':
        # 美股代码验证
        return len(symbol) <= 5 and symbol.isalpha()

    return True  # 其他市场暂时通过

def calculate_change_pct(current: Decimal, previous: Decimal) -> Optional[Decimal]:
    """
    计算涨跌幅

    Args:
        current: 当前价格
        previous: 前一价格

    Returns:
        涨跌幅百分比
    """
    if previous is None or previous == 0:
        return None

    return ((current - previous) / previous) * 100

def calculate_amplitude(high: Decimal, low: Decimal, previous_close: Decimal) -> Optional[Decimal]:
    """
    计算振幅

    Args:
        high: 最高价
        low: 最低价
        previous_close: 前收盘价

    Returns:
        振幅百分比
    """
    if previous_close is None or previous_close == 0:
        return None

    return ((high - low) / previous_close) * 100

@dataclass
class FinancialStatement:
    """
    财务报表数据模型

    对标Wind万得、Bloomberg等专业软件的财务报表结构
    支持三大财务报表：资产负债表、利润表、现金流量表
    """
    # 基础信息
    symbol: str                                 # 股票代码
    report_date: date                          # 报告期
    report_type: ReportType                    # 报表类型
    report_period: Optional[str] = None        # 报告期间描述
    fiscal_year: Optional[int] = None          # 财政年度

    # === 资产负债表 ===
    # 资产
    total_assets: Optional[Decimal] = None              # 资产总计
    current_assets: Optional[Decimal] = None            # 流动资产合计
    non_current_assets: Optional[Decimal] = None        # 非流动资产合计
    cash_and_equivalents: Optional[Decimal] = None      # 货币资金
    short_term_investments: Optional[Decimal] = None    # 短期投资
    accounts_receivable: Optional[Decimal] = None       # 应收账款
    inventory: Optional[Decimal] = None                 # 存货
    prepaid_expenses: Optional[Decimal] = None          # 预付费用
    fixed_assets: Optional[Decimal] = None              # 固定资产
    intangible_assets: Optional[Decimal] = None         # 无形资产
    goodwill: Optional[Decimal] = None                  # 商誉

    # 负债
    total_liabilities: Optional[Decimal] = None         # 负债合计
    current_liabilities: Optional[Decimal] = None       # 流动负债合计
    non_current_liabilities: Optional[Decimal] = None   # 非流动负债合计
    accounts_payable: Optional[Decimal] = None          # 应付账款
    short_term_debt: Optional[Decimal] = None           # 短期借款
    long_term_debt: Optional[Decimal] = None            # 长期借款
    accrued_expenses: Optional[Decimal] = None          # 应付费用

    # 股东权益
    shareholders_equity: Optional[Decimal] = None        # 股东权益合计
    paid_in_capital: Optional[Decimal] = None           # 实收资本
    retained_earnings: Optional[Decimal] = None         # 留存收益
    accumulated_other_comprehensive_income: Optional[Decimal] = None  # 其他综合收益

    # === 利润表 ===
    operating_revenue: Optional[Decimal] = None         # 营业收入
    operating_costs: Optional[Decimal] = None           # 营业成本
    gross_profit: Optional[Decimal] = None              # 毛利润
    operating_expenses: Optional[Decimal] = None        # 营业费用
    selling_expenses: Optional[Decimal] = None          # 销售费用
    admin_expenses: Optional[Decimal] = None            # 管理费用
    rd_expenses: Optional[Decimal] = None               # 研发费用
    financial_expenses: Optional[Decimal] = None        # 财务费用
    operating_profit: Optional[Decimal] = None          # 营业利润
    non_operating_income: Optional[Decimal] = None      # 营业外收入
    non_operating_expenses: Optional[Decimal] = None    # 营业外支出
    profit_before_tax: Optional[Decimal] = None         # 利润总额
    income_tax: Optional[Decimal] = None                # 所得税费用
    net_profit: Optional[Decimal] = None                # 净利润
    net_profit_attributable_to_parent: Optional[Decimal] = None  # 归母净利润

    # 每股指标
    eps: Optional[Decimal] = None                       # 基本每股收益
    diluted_eps: Optional[Decimal] = None               # 稀释每股收益
    book_value_per_share: Optional[Decimal] = None      # 每股净资产

    # === 现金流量表 ===
    operating_cash_flow: Optional[Decimal] = None       # 经营活动现金流量净额
    investing_cash_flow: Optional[Decimal] = None       # 投资活动现金流量净额
    financing_cash_flow: Optional[Decimal] = None       # 筹资活动现金流量净额
    net_cash_flow: Optional[Decimal] = None             # 现金及现金等价物净增加额
    free_cash_flow: Optional[Decimal] = None            # 自由现金流

    # 经营活动现金流明细
    cash_from_operations: Optional[Decimal] = None      # 销售商品收到的现金
    cash_paid_for_goods: Optional[Decimal] = None       # 购买商品支付的现金
    cash_paid_to_employees: Optional[Decimal] = None    # 支付给职工的现金
    cash_paid_for_taxes: Optional[Decimal] = None       # 支付的各项税费

    # === 财务比率 ===
    # 盈利能力比率
    roe: Optional[Decimal] = None                       # 净资产收益率
    roa: Optional[Decimal] = None                       # 总资产收益率
    roic: Optional[Decimal] = None                      # 投入资本回报率
    gross_profit_margin: Optional[Decimal] = None      # 毛利率
    operating_profit_margin: Optional[Decimal] = None  # 营业利润率
    net_profit_margin: Optional[Decimal] = None        # 净利率

    # 偿债能力比率
    current_ratio: Optional[Decimal] = None             # 流动比率
    quick_ratio: Optional[Decimal] = None               # 速动比率
    debt_to_equity: Optional[Decimal] = None            # 负债权益比
    debt_to_assets: Optional[Decimal] = None            # 资产负债率
    asset_liability_ratio: Optional[Decimal] = None     # 资产负债率（别名）
    interest_coverage: Optional[Decimal] = None         # 利息保障倍数

    # 营运能力比率
    asset_turnover: Optional[Decimal] = None            # 总资产周转率
    inventory_turnover: Optional[Decimal] = None        # 存货周转率
    receivables_turnover: Optional[Decimal] = None      # 应收账款周转率

    # 成长能力比率
    revenue_growth: Optional[Decimal] = None            # 营收增长率
    profit_growth: Optional[Decimal] = None             # 净利润增长率
    asset_growth: Optional[Decimal] = None              # 总资产增长率

    # 元数据
    plugin_specific_data: Dict[str, Any] = field(default_factory=dict)  # 插件特定数据
    data_source: str = ""                               # 数据源
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_quality_score: Optional[Decimal] = None       # 数据质量评分

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (date, datetime)):
                result[key] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, ReportType):
                result[key] = value.value
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FinancialStatement':
        """从字典创建实例"""
        # 处理日期字段
        if 'report_date' in data and isinstance(data['report_date'], str):
            data['report_date'] = datetime.fromisoformat(data['report_date']).date()

        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        # 处理枚举字段
        if 'report_type' in data and isinstance(data['report_type'], str):
            # 尝试直接转换
            try:
                data['report_type'] = ReportType(data['report_type'])
            except ValueError:
                # 如果失败，尝试映射
                report_type_mapping = {
                    'ANNUAL': ReportType.ANNUAL,
                    'SEMI_ANNUAL': ReportType.SEMI_ANNUAL,
                    'QUARTERLY': ReportType.QUARTERLY,
                    'MONTHLY': ReportType.MONTHLY,
                    'annual': ReportType.ANNUAL,
                    'semi_annual': ReportType.SEMI_ANNUAL,
                    'quarterly': ReportType.QUARTERLY,
                    'monthly': ReportType.MONTHLY
                }
                if data['report_type'] in report_type_mapping:
                    data['report_type'] = report_type_mapping[data['report_type']]
                else:
                    raise ValueError(f"无效的报表类型: {data['report_type']}")

        # 处理Decimal字段
        decimal_fields = [
            'total_assets', 'current_assets', 'non_current_assets', 'cash_and_equivalents',
            'total_liabilities', 'current_liabilities', 'non_current_liabilities',
            'shareholders_equity', 'paid_in_capital', 'retained_earnings',
            'operating_revenue', 'operating_costs', 'gross_profit', 'net_profit',
            'operating_cash_flow', 'investing_cash_flow', 'financing_cash_flow',
            'eps', 'diluted_eps', 'roe', 'roa', 'current_ratio', 'quick_ratio',
            'debt_to_equity', 'gross_profit_margin', 'net_profit_margin',
            'data_quality_score'
        ]

        for field in decimal_fields:
            if field in data and data[field] is not None:
                data[field] = Decimal(str(data[field]))

        return cls(**data)

@dataclass
class MacroEconomicData:
    """
    宏观经济数据模型

    对标Wind万得、Bloomberg等专业软件的宏观经济数据结构
    支持各类宏观经济指标：GDP、CPI、利率、汇率等
    """
    # 基础信息
    indicator_code: str                         # 指标代码
    indicator_name: str                         # 指标名称
    data_date: date                            # 数据日期
    frequency: str                             # 数据频率 (日/周/月/季/年)

    # 数据值
    value: Decimal                             # 指标值
    unit: str                                  # 单位
    category: str                              # 主分类 (GDP/CPI/利率/汇率等)
    previous_value: Optional[Decimal] = None   # 前值
    forecast_value: Optional[Decimal] = None   # 预测值

    # 分类信息
    subcategory: Optional[str] = None          # 子分类
    indicator_type: Optional[str] = None       # 指标类型 (绝对值/增长率/指数等)

    # 地理信息
    country: str = "CN"                        # 国家代码
    region: Optional[str] = None               # 地区代码
    city: Optional[str] = None                 # 城市代码

    # 数据属性
    seasonally_adjusted: bool = False          # 是否季节性调整
    is_preliminary: bool = False               # 是否初值
    is_revised: bool = False                   # 是否修正值
    revision_count: int = 0                    # 修正次数

    # 发布信息
    release_date: Optional[date] = None        # 发布日期
    release_time: Optional[str] = None         # 发布时间
    next_release_date: Optional[date] = None   # 下次发布日期

    # 数据来源
    data_source: str = ""                      # 数据源
    source_code: Optional[str] = None          # 源系统代码
    publisher: Optional[str] = None            # 发布机构

    # 统计信息
    historical_high: Optional[Decimal] = None  # 历史最高值
    historical_low: Optional[Decimal] = None   # 历史最低值
    historical_average: Optional[Decimal] = None  # 历史平均值

    # 变化率
    mom_change: Optional[Decimal] = None       # 环比变化
    yoy_change: Optional[Decimal] = None       # 同比变化
    qoq_change: Optional[Decimal] = None       # 季度环比变化

    # 元数据
    plugin_specific_data: Dict[str, Any] = field(default_factory=dict)  # 插件特定数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_quality_score: Optional[Decimal] = None  # 数据质量评分

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (date, datetime)):
                result[key] = value.isoformat()
            elif isinstance(value, Decimal):
                result[key] = str(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MacroEconomicData':
        """从字典创建实例"""
        # 处理日期字段
        date_fields = ['data_date', 'release_date', 'next_release_date']
        for field in date_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field]).date()

        datetime_fields = ['created_at', 'updated_at']
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])

        # 处理Decimal字段
        decimal_fields = [
            'value', 'previous_value', 'forecast_value', 'historical_high',
            'historical_low', 'historical_average', 'mom_change', 'yoy_change',
            'qoq_change', 'data_quality_score'
        ]

        for field in decimal_fields:
            if field in data and data[field] is not None:
                data[field] = Decimal(str(data[field]))

        return cls(**data)

    def calculate_changes(self, previous_period_value: Optional[Decimal] = None,
                          same_period_last_year_value: Optional[Decimal] = None) -> None:
        """
        计算各种变化率

        Args:
            previous_period_value: 上期值
            same_period_last_year_value: 去年同期值
        """
        # 计算环比变化
        if previous_period_value is not None and previous_period_value != 0:
            self.mom_change = ((self.value - previous_period_value) / previous_period_value) * 100

        # 计算同比变化
        if same_period_last_year_value is not None and same_period_last_year_value != 0:
            self.yoy_change = ((self.value - same_period_last_year_value) / same_period_last_year_value) * 100

# 新增工具函数
def calculate_financial_ratios(financial_data: FinancialStatement) -> FinancialStatement:
    """
    计算财务比率

    Args:
        financial_data: 财务报表数据

    Returns:
        计算完比率的财务报表数据
    """
    # 盈利能力比率
    if financial_data.net_profit and financial_data.shareholders_equity and financial_data.shareholders_equity != 0:
        financial_data.roe = financial_data.net_profit / financial_data.shareholders_equity

    if financial_data.net_profit and financial_data.total_assets and financial_data.total_assets != 0:
        financial_data.roa = financial_data.net_profit / financial_data.total_assets

    if financial_data.gross_profit and financial_data.operating_revenue and financial_data.operating_revenue != 0:
        financial_data.gross_profit_margin = financial_data.gross_profit / financial_data.operating_revenue

    if financial_data.net_profit and financial_data.operating_revenue and financial_data.operating_revenue != 0:
        financial_data.net_profit_margin = financial_data.net_profit / financial_data.operating_revenue

    # 偿债能力比率
    if financial_data.current_assets and financial_data.current_liabilities and financial_data.current_liabilities != 0:
        financial_data.current_ratio = financial_data.current_assets / financial_data.current_liabilities

    if financial_data.total_liabilities and financial_data.total_assets and financial_data.total_assets != 0:
        financial_data.debt_to_assets = financial_data.total_liabilities / financial_data.total_assets
        financial_data.asset_liability_ratio = financial_data.total_liabilities / financial_data.total_assets

    if financial_data.total_liabilities and financial_data.shareholders_equity and financial_data.shareholders_equity != 0:
        financial_data.debt_to_equity = financial_data.total_liabilities / financial_data.shareholders_equity

    return financial_data

def normalize_financial_data(data: pd.DataFrame, method: str = 'zscore') -> pd.DataFrame:
    """
    财务数据标准化

    Args:
        data: 财务数据DataFrame
        method: 标准化方法 ('zscore', 'minmax', 'robust')

    Returns:
        标准化后的数据
    """
    numeric_columns = data.select_dtypes(include=[float, int]).columns
    result = data.copy()

    if method == 'zscore':
        std_vals = result[numeric_columns].std()
        std_vals = std_vals.replace(0, 1)
        result[numeric_columns] = (result[numeric_columns] - result[numeric_columns].mean()) / std_vals
    elif method == 'minmax':
        range_vals = result[numeric_columns].max() - result[numeric_columns].min()
        range_vals = range_vals.replace(0, 1)
        result[numeric_columns] = (result[numeric_columns] - result[numeric_columns].min()) / range_vals
    elif method == 'robust':
        median = result[numeric_columns].median()
        mad = (result[numeric_columns] - median).abs().median()
        mad = mad.replace(0, 1)
        result[numeric_columns] = (result[numeric_columns] - median) / mad

    return result

def calculate_turnover_rate(volume: int, total_shares: int) -> Optional[Decimal]:
    """
    计算换手率

    Args:
        volume: 成交量
        total_shares: 总股本

    Returns:
        换手率 (小数形式，如0.1表示10%)
    """
    if total_shares is None or total_shares == 0:
        return None

    return Decimal(volume) / Decimal(total_shares)
