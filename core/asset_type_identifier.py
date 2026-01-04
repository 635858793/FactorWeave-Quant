"""
资产类型识别器

基于股票代码、交易所信息等自动识别资产类型的核心组件。
支持A股、港股、美股、数字货币、期货等多种资产类型的智能识别。

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import re
from typing import Optional, Dict, List, Tuple
from loguru import logger
from dataclasses import dataclass

from .plugin_types import AssetType


@dataclass
class IdentificationRule:
    """资产类型识别规则"""
    asset_type: AssetType
    pattern: str
    description: str
    priority: int = 100  # 优先级，数字越小优先级越高


class AssetTypeIdentifier:
    """
    资产类型识别器

    根据股票代码、交易所信息等自动识别资产类型。
    支持多种识别规则和优先级机制。
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logger.bind(module=__name__)
            self._identification_rules = self._initialize_identification_rules()
            self._symbol_cache = {}  # 缓存识别结果，提高性能
            AssetTypeIdentifier._initialized = True

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_identification_rules(self) -> List[IdentificationRule]:
        """初始化资产类型识别规则"""
        rules = [
            # A股识别规则 (优先级最高)
            IdentificationRule(
                asset_type=AssetType.STOCK_A,
                pattern=r'^(000[0-9]{3}|002[0-9]{3}|300[0-9]{3})\.(SZ|sz)$',
                description="深交所A股: 000xxx, 002xxx, 300xxx",
                priority=10
            ),
            IdentificationRule(
                asset_type=AssetType.STOCK_A,
                pattern=r'^(600[0-9]{3}|601[0-9]{3}|603[0-9]{3}|605[0-9]{3}|688[0-9]{3})\.(SH|sh)$',
                description="上交所A股: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx",
                priority=10
            ),
            # A股识别规则 (不带后缀)
            IdentificationRule(
                asset_type=AssetType.STOCK_A,
                pattern=r'^(000[0-9]{3}|002[0-9]{3}|300[0-9]{3})$',
                description="深交所A股(无后缀): 000xxx, 002xxx, 300xxx",
                priority=15
            ),
            IdentificationRule(
                asset_type=AssetType.STOCK_A,
                pattern=r'^(600[0-9]{3}|601[0-9]{3}|603[0-9]{3}|605[0-9]{3}|688[0-9]{3})$',
                description="上交所A股(无后缀): 600xxx, 601xxx, 603xxx, 605xxx, 688xxx",
                priority=15
            ),

            # B股识别规则
            IdentificationRule(
                asset_type=AssetType.STOCK_B,
                pattern=r'^(200[0-9]{3})\.(SZ|sz)$',
                description="深交所B股: 200xxx",
                priority=20
            ),
            IdentificationRule(
                asset_type=AssetType.STOCK_B,
                pattern=r'^(900[0-9]{3})\.(SH|sh)$',
                description="上交所B股: 900xxx",
                priority=20
            ),

            # 港股识别规则
            IdentificationRule(
                asset_type=AssetType.STOCK_HK,
                pattern=r'^[0-9]{4,5}\.(HK|hk)$',
                description="港股: 数字代码.HK",
                priority=30
            ),

            # 美股识别规则
            IdentificationRule(
                asset_type=AssetType.STOCK_US,
                pattern=r'^[A-Z]{1,5}$',
                description="美股: 1-5位字母代码",
                priority=40
            ),
            IdentificationRule(
                asset_type=AssetType.STOCK_US,
                pattern=r'^[A-Z]{1,5}\.(US|us|NASDAQ|nasdaq|NYSE|nyse)$',
                description="美股: 带交易所后缀",
                priority=35
            ),

            # 数字货币识别规则 (优先级高于美股)
            IdentificationRule(
                asset_type=AssetType.CRYPTO,
                pattern=r'^(BTC|ETH|USDT|USDC|BNB|ADA|XRP|SOL|DOT|AVAX|LUNA|DOGE|SHIB)$',
                description="主流数字货币",
                priority=25
            ),
            IdentificationRule(
                asset_type=AssetType.CRYPTO,
                pattern=r'^[A-Z]{1,10}(USDT|USD|BTC|ETH)$',
                description="数字货币: 以USDT/USD/BTC/ETH结尾",
                priority=30
            ),

            # 期货识别规则
            IdentificationRule(
                asset_type=AssetType.FUTURES,
                pattern=r'^(IF|IC|IH|T|TF|TS)[0-9]{4}$',
                description="中金所期货: IF/IC/IH/T/TF/TS + 年月",
                priority=60
            ),
            IdentificationRule(
                asset_type=AssetType.FUTURES,
                pattern=r'^(CU|AL|ZN|PB|NI|SN|AU|AG)[0-9]{4}$',
                description="上期所金属期货",
                priority=60
            ),
            IdentificationRule(
                asset_type=AssetType.FUTURES,
                pattern=r'^(RB|HC|FU|BU|RU|NR|SP|SC|LU)[0-9]{4}$',
                description="上期所能源化工期货",
                priority=60
            ),
            IdentificationRule(
                asset_type=AssetType.FUTURES,
                pattern=r'^(A|B|C|CS|I|J|JM|JD|L|M|P|PP|V|Y|EG|EB|PG|RR|LH|PK)[0-9]{4}$',
                description="大商所期货",
                priority=60
            ),
            IdentificationRule(
                asset_type=AssetType.FUTURES,
                pattern=r'^(WH|PM|CF|SR|TA|OI|RI|RS|RM|MA|FG|SF|SM|ZC|CY|AP|CJ|UR|SA|PF)[0-9]{4}$',
                description="郑商所期货",
                priority=60
            ),

            # 基金识别规则
            IdentificationRule(
                asset_type=AssetType.FUND,
                pattern=r'^(1[0-9]{5}|5[0-9]{5}|16[0-9]{4}|51[0-9]{4})\.(OF|of)$',
                description="开放式基金",
                priority=70
            ),
            IdentificationRule(
                asset_type=AssetType.FUND,
                pattern=r'^(15[0-9]{4}|16[0-9]{4}|50[0-9]{4}|51[0-9]{4}|52[0-9]{4})\.(SZ|SH|sz|sh)$',
                description="ETF基金",
                priority=65
            ),

            # 债券识别规则
            IdentificationRule(
                asset_type=AssetType.BOND,
                pattern=r'^(10[0-9]{4}|11[0-9]{4}|12[0-9]{4}|13[0-9]{4})\.(SH|sh)$',
                description="上交所债券",
                priority=80
            ),
            IdentificationRule(
                asset_type=AssetType.BOND,
                pattern=r'^(12[0-9]{4}|13[0-9]{4})\.(SZ|sz)$',
                description="深交所债券",
                priority=80
            ),

            # 指数识别规则
            IdentificationRule(
                asset_type=AssetType.INDEX,
                pattern=r'^(00[0-9]{4}|39[0-9]{4})\.(SH|SZ|sh|sz)$',
                description="指数代码",
                priority=90
            ),

            # 默认股票类型 (优先级最低)
            IdentificationRule(
                asset_type=AssetType.STOCK_A,
                pattern=r'^[A-Za-z0-9]+.*$',
                description="通用股票代码",
                priority=999
            ),
        ]

        # 按优先级排序
        return sorted(rules, key=lambda x: x.priority)

    def identify_asset_type_by_symbol(self, symbol: str) -> AssetType:
        """根据股票代码识别资产类型"""
        return self._identify_asset_type_by_symbol_internal(symbol)

    def identify_asset_type(self, symbol: str) -> AssetType:
        """根据股票代码识别资产类型 (别名方法)"""
        return self.identify_asset_type_by_symbol(symbol)

    def _identify_asset_type_by_symbol_internal(self, symbol: str) -> AssetType:
        """
        根据股票代码识别资产类型

        Args:
            symbol: 股票代码，如 "000001.SZ", "AAPL", "BTCUSDT" 等

        Returns:
            AssetType: 识别出的资产类型
        """
        if not symbol or not isinstance(symbol, str):
            self.logger.warning(f"无效的股票代码: {symbol}")
            return AssetType.STOCK_A

        # 检查缓存
        symbol_upper = symbol.upper().strip()
        if symbol_upper in self._symbol_cache:
            return self._symbol_cache[symbol_upper]

        # 遍历识别规则
        for rule in self._identification_rules:
            if re.match(rule.pattern, symbol_upper):
                self.logger.debug(f"股票代码 {symbol} 匹配规则: {rule.description} -> {rule.asset_type.value}")
                self._symbol_cache[symbol_upper] = rule.asset_type
                return rule.asset_type

        # 如果没有匹配到任何规则，返回默认股票类型
        self.logger.warning(f"无法识别股票代码 {symbol} 的资产类型，使用默认股票类型")
        self._symbol_cache[symbol_upper] = AssetType.STOCK_A
        return AssetType.STOCK_A

    def identify_asset_type_by_exchange(self, symbol: str, exchange: str) -> AssetType:
        """
        根据股票代码和交易所信息识别资产类型

        Args:
            symbol: 股票代码
            exchange: 交易所代码，如 "SSE", "SZSE", "NASDAQ", "NYSE" 等

        Returns:
            AssetType: 识别出的资产类型
        """
        if not exchange:
            return self.identify_asset_type_by_symbol(symbol)

        exchange_upper = exchange.upper()

        # 交易所映射规则
        exchange_mapping = {
            "SSE": AssetType.STOCK_A,      # 上海证券交易所
            "SZSE": AssetType.STOCK_A,     # 深圳证券交易所
            "SH": AssetType.STOCK_A,
            "SZ": AssetType.STOCK_A,
            "HKEX": AssetType.STOCK_HK,    # 香港交易所
            "HK": AssetType.STOCK_HK,
            "NASDAQ": AssetType.STOCK_US,  # 纳斯达克
            "NYSE": AssetType.STOCK_US,    # 纽约证券交易所
            "AMEX": AssetType.STOCK_US,    # 美国证券交易所
            "US": AssetType.STOCK_US,
            "BINANCE": AssetType.CRYPTO,   # 币安
            "HUOBI": AssetType.CRYPTO,     # 火币
            "OKEX": AssetType.CRYPTO,      # OKEx
            "COINBASE": AssetType.CRYPTO,  # Coinbase
            "CFFEX": AssetType.FUTURES,    # 中金所
            "SHFE": AssetType.FUTURES,     # 上期所
            "DCE": AssetType.FUTURES,      # 大商所
            "CZCE": AssetType.FUTURES,     # 郑商所
        }

        if exchange_upper in exchange_mapping:
            asset_type = exchange_mapping[exchange_upper]
            self.logger.debug(f"根据交易所 {exchange} 识别股票 {symbol} 为 {asset_type.value}")
            return asset_type

        # 如果交易所信息无法识别，回退到根据代码识别
        return self.identify_asset_type_by_symbol(symbol)

    def batch_identify_asset_types(self, symbols: List[str]) -> Dict[str, AssetType]:
        """
        批量识别股票代码的资产类型

        Args:
            symbols: 股票代码列表

        Returns:
            Dict[str, AssetType]: 股票代码到资产类型的映射
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.identify_asset_type_by_symbol(symbol)

        self.logger.info(f"批量识别完成，处理了 {len(symbols)} 个股票代码")
        return results

    def get_asset_type_statistics(self, symbols: List[str]) -> Dict[AssetType, List[str]]:
        """
        获取股票代码按资产类型的统计信息

        Args:
            symbols: 股票代码列表

        Returns:
            Dict[AssetType, List[str]]: 资产类型到股票代码列表的映射
        """
        statistics = {}
        for symbol in symbols:
            asset_type = self.identify_asset_type_by_symbol(symbol)
            if asset_type not in statistics:
                statistics[asset_type] = []
            statistics[asset_type].append(symbol)

        # 记录统计信息
        for asset_type, symbol_list in statistics.items():
            self.logger.info(f"资产类型 {asset_type.value}: {len(symbol_list)} 个代码")

        return statistics

    def is_valid_symbol(self, symbol: str) -> bool:
        """
        检查股票代码是否有效

        Args:
            symbol: 股票代码

        Returns:
            bool: 是否有效
        """
        if not symbol or not isinstance(symbol, str):
            return False

        # 基本格式检查
        symbol_clean = symbol.strip()
        if len(symbol_clean) < 1 or len(symbol_clean) > 20:
            return False

        # 检查是否能识别出有效的资产类型
        try:
            asset_type = self.identify_asset_type_by_symbol(symbol)
            return asset_type is not None
        except Exception as e:
            self.logger.error(f"验证股票代码 {symbol} 时出错: {e}")
            return False

    def get_database_for_asset_type(self, asset_type: AssetType) -> str:
        """
        根据资产类型获取对应的数据库名称

        Args:
            asset_type: 资产类型

        Returns:
            str: 数据库文件名
        """
        database_mapping = {
            # ✅ 股票相关资产类型 -> 对应的独立数据库 (与 AssetDatabaseManager 动态路径保持一致)
            AssetType.STOCK_A: "stock_a_data.duckdb",
            AssetType.STOCK_B: "stock_b_data.duckdb",
            AssetType.STOCK_HK: "stock_hk_data.duckdb",
            AssetType.STOCK_US: "stock_us_data.duckdb",
            AssetType.STOCK_H: "stock_h_data.duckdb",

            # ✅ 其他资产类型 -> 专用数据库 (与 AssetDatabaseManager 动态路径保持一致)
            AssetType.FUTURES: "futures_data.duckdb",
            AssetType.CRYPTO: "crypto_data.duckdb",
            AssetType.FOREX: "forex_data.duckdb",
            AssetType.BOND: "bond_data.duckdb",
            AssetType.FUND: "fund_data.duckdb",
            AssetType.INDEX: "index_data.duckdb",
            AssetType.COMMODITY: "commodity_data.duckdb",
            AssetType.MACRO: "macro_data.duckdb",
            AssetType.OPTION: "option_data.duckdb",
            AssetType.WARRANT: "warrant_data.duckdb",

            # ✅ 板块数据 -> 对应的独立数据库
            AssetType.SECTOR: "sector_data.duckdb",
            AssetType.INDUSTRY_SECTOR: "industry_sector_data.duckdb",
            AssetType.CONCEPT_SECTOR: "concept_sector_data.duckdb",
            AssetType.STYLE_SECTOR: "style_sector_data.duckdb",
            AssetType.THEME_SECTOR: "theme_sector_data.duckdb",
        }

        return database_mapping.get(asset_type, "unknown_data.duckdb")

    def clear_cache(self):
        """清除识别结果缓存"""
        self._symbol_cache.clear()
        self.logger.info("已清除资产类型识别缓存")

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._symbol_cache),
            "total_rules": len(self._identification_rules)
        }


# 单例模式，提供全局访问点
_global_identifier = None


def get_asset_type_identifier() -> AssetTypeIdentifier:
    """获取全局资产类型识别器实例"""
    global _global_identifier
    if _global_identifier is None:
        _global_identifier = AssetTypeIdentifier()
    return _global_identifier

# 便捷函数


def identify_asset_type(symbol: str) -> AssetType:
    """便捷函数：识别单个股票代码的资产类型"""
    return get_asset_type_identifier().identify_asset_type_by_symbol(symbol)


def get_asset_type_identifier() -> AssetTypeIdentifier:
    """获取资产类型识别器实例"""
    return AssetTypeIdentifier.get_instance()


def batch_identify_asset_types(symbols: List[str]) -> Dict[str, AssetType]:
    """便捷函数：批量识别股票代码的资产类型"""
    return get_asset_type_identifier().batch_identify_asset_types(symbols)
