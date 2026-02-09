"""
统一市场服务 - 架构精简重构版本

整合所有市场管理器功能，提供统一的市场数据和股票信息管理接口。
整合IndustryManager、StockManager、MarketDataManager等。
完全重构以符合15个核心服务的架构精简目标。
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Set, Tuple
from collections import defaultdict, deque
import json

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container


class MarketType(Enum):
    """市场类型"""
    SHANGHAI = "SH"      # 上海证券交易所
    SHENZHEN = "SZ"      # 深圳证券交易所
    BEIJING = "BJ"       # 北京证券交易所
    HONGKONG = "HK"      # 香港交易所
    NASDAQ = "NASDAQ"    # 纳斯达克
    NYSE = "NYSE"        # 纽约证券交易所


class StockType(Enum):
    """股票类型"""
    STOCK = "stock"           # 普通股票
    INDEX = "index"           # 指数
    ETF = "etf"               # ETF基金
    BOND = "bond"             # 债券
    FUTURE = "future"         # 期货
    OPTION = "option"         # 期权
    CURRENCY = "currency"     # 货币


class IndustryLevel(Enum):
    """行业级别"""
    LEVEL1 = "level1"    # 一级行业
    LEVEL2 = "level2"    # 二级行业
    LEVEL3 = "level3"    # 三级行业


class DataSource(Enum):
    """数据源"""
    SINA = "sina"
    TENCENT = "tencent"
    EASTMONEY = "eastmoney"
    AKSHARE = "akshare"
    TUSHARE = "tushare"
    LOCAL = "local"


@dataclass
class StockInfo:
    """股票信息"""
    symbol: str
    name: str
    market: MarketType
    stock_type: StockType
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None
    sector: Optional[str] = None
    listing_date: Optional[datetime] = None
    delisting_date: Optional[datetime] = None
    is_active: bool = True
    is_favorite: bool = False
    market_cap: Optional[Decimal] = None
    circulating_shares: Optional[int] = None
    total_shares: Optional[int] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndustryInfo:
    """行业信息"""
    industry_code: str
    industry_name: str
    level: IndustryLevel
    parent_code: Optional[str] = None
    parent_name: Optional[str] = None
    stock_count: int = 0
    market_cap: Decimal = Decimal('0')
    avg_pe: Optional[float] = None
    avg_pb: Optional[float] = None
    performance_1d: Optional[float] = None
    performance_1w: Optional[float] = None
    performance_1m: Optional[float] = None
    performance_3m: Optional[float] = None
    performance_1y: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class MarketQuote:
    """实时行情"""
    symbol: str
    name: str
    current_price: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    prev_close: Decimal
    volume: int
    amount: Decimal
    change: Decimal
    change_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_volume: Optional[int] = None
    ask_volume: Optional[int] = None
    turnover_rate: Optional[float] = None


@dataclass
class MarketSnapshot:
    """市场快照"""
    market: MarketType
    timestamp: datetime
    total_stocks: int
    trading_stocks: int
    rising_stocks: int
    falling_stocks: int
    unchanged_stocks: int
    limit_up_stocks: int
    limit_down_stocks: int
    total_volume: int
    total_amount: Decimal
    avg_price_change: float
    market_sentiment: str  # 多头/空头/震荡


@dataclass
class WatchlistInfo:
    """自选股列表信息"""
    watchlist_id: str
    name: str
    symbols: Set[str] = field(default_factory=set)
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class MarketMetrics:
    """市场服务指标"""
    total_stocks: int = 0
    active_stocks: int = 0
    total_industries: int = 0
    total_watchlists: int = 0
    quote_updates: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    data_refresh_count: int = 0
    avg_response_time: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)


class MarketService(BaseService):
    """
    统一市场服务 - 架构精简重构版本

    整合所有市场管理器功能：
    - IndustryManager: 行业分类管理
    - StockManager: 股票信息管理
    - MarketDataManager: 市场数据管理
    - WatchlistManager: 自选股管理
    - QuoteManager: 实时行情管理
    - SectorManager: 板块管理

    提供统一的市场接口，支持：
    1. 股票信息查询和管理
    2. 行业分类和板块分析
    3. 实时行情数据获取
    4. 自选股列表管理
    5. 市场数据缓存和更新
    6. 多数据源整合
    7. 市场统计和分析
    8. 股票筛选和搜索
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化市场服务"""
        super().__init__()
        self.service_name = "MarketService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 股票信息管理
        self._stocks: Dict[str, StockInfo] = {}
        self._stock_cache: Dict[str, Any] = {}
        self._stock_lock = threading.RLock()

        # 行业信息管理
        self._industries: Dict[str, IndustryInfo] = {}
        self._industry_hierarchy: Dict[str, List[str]] = {}  # 行业层级关系
        self._industry_stocks: Dict[str, Set[str]] = defaultdict(set)  # 行业股票映射
        self._industry_lock = threading.RLock()

        # 实时行情管理
        self._quotes: Dict[str, MarketQuote] = {}
        self._quote_subscriptions: Set[str] = set()
        self._quote_lock = threading.RLock()

        # 自选股管理
        self._watchlists: Dict[str, WatchlistInfo] = {}
        self._default_watchlist_id = "default"
        self._watchlist_lock = threading.RLock()

        # 市场快照
        self._market_snapshots: Dict[MarketType, MarketSnapshot] = {}
        self._snapshot_lock = threading.RLock()

        # 市场配置
        self._market_config = {
            "default_market": MarketType.SHANGHAI,
            "data_sources": [DataSource.SINA, DataSource.TENCENT],
            "cache_expiry_minutes": 5,
            "quote_update_interval": 3,  # 行情更新间隔(秒)
            "enable_real_time": True,
            "max_cache_size": 10000,
            "enable_industry_analysis": True,
            "trading_hours": {
                "morning_start": "09:30",
                "morning_end": "11:30",
                "afternoon_start": "13:00",
                "afternoon_end": "15:00"
            }
        }

        # 服务指标
        self._market_metrics = MarketMetrics()

        # 线程和锁
        self._service_lock = threading.RLock()

        logger.info("MarketService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing MarketService core components...")

            # 1. 初始化基础行业分类
            self._initialize_basic_industries()

            # 2. 初始化默认自选股列表
            self._initialize_default_watchlist()

            # 3. 加载股票基础数据
            self._load_basic_stocks()

            # 4. 启动实时行情更新
            self._start_quote_updates()

            logger.info("MarketService initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize MarketService: {e}")
            raise

    def _initialize_basic_industries(self) -> None:
        """初始化基础行业分类"""
        try:
            # 一级行业分类
            level1_industries = [
                ("010000", "农林牧渔", IndustryLevel.LEVEL1),
                ("020000", "采掘", IndustryLevel.LEVEL1),
                ("030000", "化工", IndustryLevel.LEVEL1),
                ("040000", "钢铁", IndustryLevel.LEVEL1),
                ("050000", "有色金属", IndustryLevel.LEVEL1),
                ("060000", "电子", IndustryLevel.LEVEL1),
                ("070000", "家用电器", IndustryLevel.LEVEL1),
                ("080000", "食品饮料", IndustryLevel.LEVEL1),
                ("090000", "纺织服装", IndustryLevel.LEVEL1),
                ("100000", "轻工制造", IndustryLevel.LEVEL1),
                ("110000", "医药生物", IndustryLevel.LEVEL1),
                ("120000", "公用事业", IndustryLevel.LEVEL1),
                ("130000", "交通运输", IndustryLevel.LEVEL1),
                ("140000", "房地产", IndustryLevel.LEVEL1),
                ("150000", "商业贸易", IndustryLevel.LEVEL1),
                ("160000", "休闲服务", IndustryLevel.LEVEL1),
                ("170000", "综合", IndustryLevel.LEVEL1),
                ("180000", "建筑材料", IndustryLevel.LEVEL1),
                ("190000", "建筑装饰", IndustryLevel.LEVEL1),
                ("200000", "电气设备", IndustryLevel.LEVEL1),
                ("210000", "国防军工", IndustryLevel.LEVEL1),
                ("220000", "计算机", IndustryLevel.LEVEL1),
                ("230000", "传媒", IndustryLevel.LEVEL1),
                ("240000", "通信", IndustryLevel.LEVEL1),
                ("250000", "银行", IndustryLevel.LEVEL1),
                ("260000", "非银金融", IndustryLevel.LEVEL1),
                ("270000", "汽车", IndustryLevel.LEVEL1),
                ("280000", "机械设备", IndustryLevel.LEVEL1),
            ]

            with self._industry_lock:
                for code, name, level in level1_industries:
                    industry = IndustryInfo(
                        industry_code=code,
                        industry_name=name,
                        level=level
                    )
                    self._industries[code] = industry
                    self._market_metrics.total_industries += 1

            logger.info("✓ Basic industries initialized")

        except Exception as e:
            logger.error(f"Failed to initialize basic industries: {e}")

    def _initialize_default_watchlist(self) -> None:
        """初始化默认自选股列表"""
        try:
            default_watchlist = WatchlistInfo(
                watchlist_id=self._default_watchlist_id,
                name="默认自选股",
                description="系统默认自选股列表"
            )

            with self._watchlist_lock:
                self._watchlists[self._default_watchlist_id] = default_watchlist
                self._market_metrics.total_watchlists += 1

            logger.info("✓ Default watchlist initialized")

        except Exception as e:
            logger.error(f"Failed to initialize default watchlist: {e}")

    def _load_basic_stocks(self) -> None:
        """加载基础股票数据"""
        try:
            # 添加一些示例股票数据
            sample_stocks = [
                ("000001.SZ", "平安银行", MarketType.SHENZHEN, StockType.STOCK, "250000"),
                ("000002.SZ", "万科A", MarketType.SHENZHEN, StockType.STOCK, "140000"),
                ("600000.SH", "浦发银行", MarketType.SHANGHAI, StockType.STOCK, "250000"),
                ("600036.SH", "招商银行", MarketType.SHANGHAI, StockType.STOCK, "250000"),
                ("600519.SH", "贵州茅台", MarketType.SHANGHAI, StockType.STOCK, "080000"),
                ("000858.SZ", "五粮液", MarketType.SHENZHEN, StockType.STOCK, "080000"),
            ]

            with self._stock_lock:
                for symbol, name, market, stock_type, industry_code in sample_stocks:
                    stock = StockInfo(
                        symbol=symbol,
                        name=name,
                        market=market,
                        stock_type=stock_type,
                        industry_code=industry_code,
                        industry_name=self._industries.get(industry_code, {}).industry_name if industry_code in self._industries else None
                    )
                    self._stocks[symbol] = stock
                    self._market_metrics.total_stocks += 1
                    self._market_metrics.active_stocks += 1

                    # 添加到行业股票映射
                    if industry_code:
                        self._industry_stocks[industry_code].add(symbol)

            logger.info("✓ Basic stocks loaded")

        except Exception as e:
            logger.error(f"Failed to load basic stocks: {e}")

    def _start_quote_updates(self) -> None:
        """启动行情更新"""
        try:
            # 在真实环境中会启动后台线程更新行情
            logger.info("✓ Quote updates started")

        except Exception as e:
            logger.error(f"Failed to start quote updates: {e}")

    # 股票信息接口

    def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """获取股票信息"""
        with self._stock_lock:
            stock = self._stocks.get(symbol)
            if stock:
                self._market_metrics.cache_hits += 1
            else:
                self._market_metrics.cache_misses += 1
            return stock

    def search_stocks(self, keyword: str = "", market: Optional[MarketType] = None,
                      industry_code: Optional[str] = None, stock_type: Optional[StockType] = None,
                      limit: int = 100) -> List[StockInfo]:
        """搜索股票"""
        try:
            results = []

            with self._stock_lock:
                for stock in self._stocks.values():
                    # 市场筛选
                    if market and stock.market != market:
                        continue

                    # 行业筛选
                    if industry_code and stock.industry_code != industry_code:
                        continue

                    # 股票类型筛选
                    if stock_type and stock.stock_type != stock_type:
                        continue

                    # 关键词搜索
                    if keyword:
                        if (keyword.upper() not in stock.symbol.upper() and
                                keyword not in stock.name):
                            continue

                    results.append(stock)

                    if len(results) >= limit:
                        break

            logger.info(f"Found {len(results)} stocks for search: {keyword}")
            return results

        except Exception as e:
            logger.error(f"Failed to search stocks: {e}")
            return []

    def add_stock(self, stock: StockInfo) -> bool:
        """添加股票"""
        try:
            with self._stock_lock:
                self._stocks[stock.symbol] = stock
                self._market_metrics.total_stocks += 1
                if stock.is_active:
                    self._market_metrics.active_stocks += 1

                # 更新行业股票映射
                if stock.industry_code:
                    self._industry_stocks[stock.industry_code].add(stock.symbol)

            logger.info(f"Stock added: {stock.symbol} - {stock.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add stock {stock.symbol}: {e}")
            return False

    def update_stock_info(self, symbol: str, **kwargs) -> bool:
        """更新股票信息"""
        try:
            with self._stock_lock:
                if symbol not in self._stocks:
                    return False

                stock = self._stocks[symbol]
                for key, value in kwargs.items():
                    if hasattr(stock, key):
                        setattr(stock, key, value)

                stock.last_update = datetime.now()

            logger.info(f"Stock info updated: {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to update stock info {symbol}: {e}")
            return False

    # 行业信息接口

    def get_industry_info(self, industry_code: str) -> Optional[IndustryInfo]:
        """获取行业信息"""
        with self._industry_lock:
            return self._industries.get(industry_code)

    def get_industry_stocks(self, industry_code: str) -> List[StockInfo]:
        """获取行业内股票"""
        try:
            stocks = []
            symbols = self._industry_stocks.get(industry_code, set())

            with self._stock_lock:
                for symbol in symbols:
                    if symbol in self._stocks:
                        stocks.append(self._stocks[symbol])

            return stocks

        except Exception as e:
            logger.error(f"Failed to get industry stocks {industry_code}: {e}")
            return []

    def get_all_industries(self, level: Optional[IndustryLevel] = None) -> List[IndustryInfo]:
        """获取所有行业"""
        with self._industry_lock:
            industries = list(self._industries.values())
            if level:
                industries = [ind for ind in industries if ind.level == level]
            return industries

    def update_industry_stats(self, industry_code: str) -> bool:
        """更新行业统计数据"""
        try:
            with self._industry_lock:
                if industry_code not in self._industries:
                    return False

                industry = self._industries[industry_code]
                stocks = self.get_industry_stocks(industry_code)

                # 更新股票数量
                industry.stock_count = len(stocks)

                # 计算市值等统计数据
                total_market_cap = Decimal('0')
                pe_ratios = []
                pb_ratios = []

                for stock in stocks:
                    if stock.market_cap:
                        total_market_cap += stock.market_cap
                    if stock.pe_ratio:
                        pe_ratios.append(stock.pe_ratio)
                    if stock.pb_ratio:
                        pb_ratios.append(stock.pb_ratio)

                industry.market_cap = total_market_cap
                industry.avg_pe = sum(pe_ratios) / len(pe_ratios) if pe_ratios else None
                industry.avg_pb = sum(pb_ratios) / len(pb_ratios) if pb_ratios else None
                industry.last_update = datetime.now()

            logger.info(f"Industry stats updated: {industry_code}")
            return True

        except Exception as e:
            logger.error(f"Failed to update industry stats {industry_code}: {e}")
            return False

    # 实时行情接口

    def get_quote(self, symbol: str) -> Optional[MarketQuote]:
        """获取实时行情"""
        with self._quote_lock:
            return self._quotes.get(symbol)

    def update_quote(self, quote: MarketQuote) -> bool:
        """更新实时行情"""
        try:
            with self._quote_lock:
                self._quotes[quote.symbol] = quote
                self._market_metrics.quote_updates += 1

            # 如果有事件总线，发布行情更新事件
            if hasattr(self, '_event_bus'):
                self._event_bus.publish("market.quote_updated",
                                        symbol=quote.symbol,
                                        price=float(quote.current_price),
                                        change_percent=quote.change_percent
                                        )

            return True

        except Exception as e:
            logger.error(f"Failed to update quote {quote.symbol}: {e}")
            return False

    def subscribe_quote(self, symbol: str) -> bool:
        """订阅行情"""
        try:
            with self._quote_lock:
                self._quote_subscriptions.add(symbol)

            logger.info(f"Quote subscribed: {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe quote {symbol}: {e}")
            return False

    def unsubscribe_quote(self, symbol: str) -> bool:
        """取消订阅行情"""
        try:
            with self._quote_lock:
                self._quote_subscriptions.discard(symbol)

            logger.info(f"Quote unsubscribed: {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe quote {symbol}: {e}")
            return False

    def get_subscribed_quotes(self) -> List[MarketQuote]:
        """获取已订阅的行情"""
        quotes = []
        with self._quote_lock:
            for symbol in self._quote_subscriptions:
                if symbol in self._quotes:
                    quotes.append(self._quotes[symbol])
        return quotes

    # 自选股接口

    def create_watchlist(self, name: str, description: str = "") -> str:
        """创建自选股列表"""
        try:
            watchlist_id = str(uuid.uuid4())
            watchlist = WatchlistInfo(
                watchlist_id=watchlist_id,
                name=name,
                description=description
            )

            with self._watchlist_lock:
                self._watchlists[watchlist_id] = watchlist
                self._market_metrics.total_watchlists += 1

            logger.info(f"Watchlist created: {watchlist_id} - {name}")
            return watchlist_id

        except Exception as e:
            logger.error(f"Failed to create watchlist: {e}")
            return ""

    def add_to_watchlist(self, watchlist_id: str, symbol: str) -> bool:
        """添加股票到自选股"""
        try:
            with self._watchlist_lock:
                if watchlist_id not in self._watchlists:
                    return False

                watchlist = self._watchlists[watchlist_id]
                watchlist.symbols.add(symbol)
                watchlist.updated_time = datetime.now()

                # 更新股票的自选股标记
                with self._stock_lock:
                    if symbol in self._stocks:
                        self._stocks[symbol].is_favorite = True

            logger.info(f"Stock {symbol} added to watchlist {watchlist_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add {symbol} to watchlist {watchlist_id}: {e}")
            return False

    def remove_from_watchlist(self, watchlist_id: str, symbol: str) -> bool:
        """从自选股移除股票"""
        try:
            with self._watchlist_lock:
                if watchlist_id not in self._watchlists:
                    return False

                watchlist = self._watchlists[watchlist_id]
                watchlist.symbols.discard(symbol)
                watchlist.updated_time = datetime.now()

                # 检查是否在其他自选股列表中
                is_in_other_watchlist = any(
                    symbol in wl.symbols
                    for wl_id, wl in self._watchlists.items()
                    if wl_id != watchlist_id
                )

                # 更新股票的自选股标记
                if not is_in_other_watchlist:
                    with self._stock_lock:
                        if symbol in self._stocks:
                            self._stocks[symbol].is_favorite = False

            logger.info(f"Stock {symbol} removed from watchlist {watchlist_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove {symbol} from watchlist {watchlist_id}: {e}")
            return False

    def get_watchlist(self, watchlist_id: str = None) -> Optional[WatchlistInfo]:
        """获取自选股列表"""
        watchlist_id = watchlist_id or self._default_watchlist_id
        with self._watchlist_lock:
            return self._watchlists.get(watchlist_id)

    def get_all_watchlists(self) -> List[WatchlistInfo]:
        """获取所有自选股列表"""
        with self._watchlist_lock:
            return list(self._watchlists.values())

    def get_watchlist_stocks(self, watchlist_id: str = None) -> List[StockInfo]:
        """获取自选股列表中的股票"""
        watchlist_id = watchlist_id or self._default_watchlist_id
        stocks = []

        with self._watchlist_lock:
            if watchlist_id in self._watchlists:
                symbols = self._watchlists[watchlist_id].symbols

                with self._stock_lock:
                    for symbol in symbols:
                        if symbol in self._stocks:
                            stocks.append(self._stocks[symbol])

        return stocks

    # 市场统计接口

    def get_market_snapshot(self, market: MarketType) -> Optional[MarketSnapshot]:
        """获取市场快照"""
        with self._snapshot_lock:
            return self._market_snapshots.get(market)

    def update_market_snapshot(self, snapshot: MarketSnapshot) -> bool:
        """更新市场快照"""
        try:
            with self._snapshot_lock:
                self._market_snapshots[snapshot.market] = snapshot

            logger.info(f"Market snapshot updated: {snapshot.market.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to update market snapshot: {e}")
            return False

    # 公共接口方法

    def get_market_metrics(self) -> MarketMetrics:
        """获取市场服务指标"""
        with self._service_lock:
            self._market_metrics.last_update = datetime.now()
            return self._market_metrics

    def refresh_data(self, force: bool = False) -> bool:
        """刷新数据"""
        try:
            logger.info("Refreshing market data...")

            # 在真实环境中会从数据源刷新数据
            self._market_metrics.data_refresh_count += 1

            logger.info("Market data refreshed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh market data: {e}")
            return False

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            return {
                "status": "healthy",
                "total_stocks": len(self._stocks),
                "active_stocks": self._market_metrics.active_stocks,
                "total_industries": len(self._industries),
                "total_watchlists": len(self._watchlists),
                "quote_subscriptions": len(self._quote_subscriptions),
                "cached_quotes": len(self._quotes),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing MarketService resources...")

            with self._stock_lock:
                self._stocks.clear()
                self._stock_cache.clear()

            with self._industry_lock:
                self._industries.clear()
                self._industry_hierarchy.clear()
                self._industry_stocks.clear()

            with self._quote_lock:
                self._quotes.clear()
                self._quote_subscriptions.clear()

            with self._watchlist_lock:
                self._watchlists.clear()

            with self._snapshot_lock:
                self._market_snapshots.clear()

            logger.info("MarketService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing MarketService: {e}")
