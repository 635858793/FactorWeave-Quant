"""
miniQMT数据源插件

提供miniQMT实时行情数据接入，支持A股、港股、美股等市场。
基于FactorWeave-Quant标准插件模板实现，集成xtdata接口。

功能特性：
- 实时行情推送
- Level-2行情数据
- Tick数据
- K线数据
- 多市场支持

作者: FactorWeave-Quant团队
版本: 1.0.0
日期: 2025-01-16
"""

import asyncio
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from loguru import logger

from plugins.templates.standard_data_source_plugin import (
    StandardDataSourcePlugin, PluginConfig,
    PluginConnectionError, PluginDataQualityError
)
from core.plugin_types import AssetType, DataType
from core.data_source_extensions import PluginInfo, HealthCheckResult, ConnectionInfo

try:
    import xtquant.xtdata as xtdata
    XTQUANT_AVAILABLE = True
except ImportError:
    XTQUANT_AVAILABLE = False
    logger.warning("xtquant (miniQMT) 未安装，miniQMT功能不可用")


@dataclass
class MiniQMTConfig(PluginConfig):
    """miniQMT插件配置"""

    def __init__(self):
        super().__init__()

        # miniQMT连接配置
        self.session_id = 0
        self.ip = "127.0.0.1"
        self.port = 58610

        # 数据类型支持
        self.supported_data_types = [
            DataType.REAL_TIME_QUOTE,
            DataType.TICK_DATA,
            DataType.HISTORICAL_KLINE,
            DataType.LEVEL2_DATA
        ]

        # 资产类型支持
        self.supported_asset_types = [
            AssetType.STOCK_A,
            AssetType.STOCK_HK,
            AssetType.STOCK_US,
            AssetType.INDEX,
            AssetType.FUND
        ]

        # 市场配置
        self.market_config = {
            'SH': 'SH',  # 上海
            'SZ': 'SZ',  # 深圳
            'HK': 'HK',  # 香港
            'US': 'US'   # 美国
        }

        # 性能配置
        self.max_symbols_per_subscription = 500
        self.data_buffer_size = 10000
        self.heartbeat_interval = 30
        self.reconnect_interval = 5

        # 缓存配置
        self.enable_cache = True
        self.cache_ttl = 60


class MiniQMTPlugin(StandardDataSourcePlugin):
    """miniQMT数据源插件"""

    def __init__(self):
        super().__init__(
            plugin_id="miniqmt_data_source",
            plugin_name="miniQMT数据源"
        )
        self.config = MiniQMTConfig()

        # 存储插件信息
        self._plugin_info = PluginInfo(
            id="miniqmt_data_source",
            name="miniQMT数据源",
            version="1.0.0",
            author="FactorWeave-Quant团队",
            description="提供miniQMT实时行情数据接入",
            supported_asset_types=self.config.supported_asset_types,
            supported_data_types=self.config.supported_data_types,
            capabilities={}
        )

        # xtdata连接
        self._xtdata = None
        self._connected = False

        # 订阅管理
        self._subscriptions: Dict[str, List[str]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

        # 数据缓存
        self._quote_cache: Dict[str, Dict] = {}
        self._tick_cache: Dict[str, List[Dict]] = {}
        self._kline_cache: Dict[str, pd.DataFrame] = {}

        # 实时数据推送线程
        self._push_thread = None
        self._push_running = False
        self._push_interval = 0.1  # 100ms

        # 性能统计
        self._stats = {
            'total_quotes': 0,
            'total_ticks': 0,
            'last_update_time': None
        }

        self.logger.info("miniQMT数据源插件初始化完成")

    def connect(self) -> bool:
        """连接miniQMT"""
        return self._internal_connect()

    def disconnect(self) -> bool:
        """断开连接"""
        return self._internal_disconnect()

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self._is_connected

    def subscribe_realtime_data(self, symbols: List[str], callback: Callable) -> bool:
        """订阅实时数据"""
        try:
            self.logger.info(f"订阅实时数据: {symbols}")

            for symbol in symbols:
                if symbol not in self._callbacks:
                    self._callbacks[symbol] = []

                self._callbacks[symbol].append(callback)

                # 订阅实时行情
                if self._xtdata:
                    self._xtdata.subscribe_quote(
                        stock_code=symbol,
                        period='tick',
                        callback=self._on_quote_update
                    )

                    if symbol not in self._subscriptions:
                        self._subscriptions[symbol] = []
                    self._subscriptions[symbol].append('quote')

            # 启动数据推送线程
            if not self._push_running:
                self._start_push_thread()

            return True

        except Exception as e:
            self.logger.error(f"订阅实时数据失败: {e}")
            return False

    def unsubscribe_realtime_data(self, symbols: List[str]) -> bool:
        """取消订阅实时数据"""
        try:
            self.logger.info(f"取消订阅实时数据: {symbols}")

            for symbol in symbols:
                if symbol in self._callbacks:
                    del self._callbacks[symbol]

                if self._xtdata and symbol in self._subscriptions:
                    self._xtdata.unsubscribe_quote(symbol, 'tick')
                    del self._subscriptions[symbol]

            return True

        except Exception as e:
            self.logger.error(f"取消订阅实时数据失败: {e}")
            return False

    def get_realtime_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        try:
            if not self._xtdata:
                return None

            # 从缓存获取
            if symbol in self._quote_cache:
                return self._quote_cache[symbol]

            # 从miniQMT获取
            quote_data = self._xtdata.get_market_data(
                stock_list=[symbol],
                period='tick',
                count=1
            )

            if quote_data and not quote_data.empty:
                quote_dict = self._convert_quote_to_dict(quote_data, symbol)
                self._quote_cache[symbol] = quote_dict
                return quote_dict

            return None

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {symbol}, {e}")
            return None

    def get_tick_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        asset_type: AssetType = None
    ) -> pd.DataFrame:
        """获取tick数据（兼容 EnhancedRealtimeDataManager 接口）"""
        try:
            if not self._xtdata:
                return pd.DataFrame()

            # 从缓存获取
            if symbol in self._tick_cache:
                tick_list = self._tick_cache[symbol]

                # 过滤时间范围
                filtered_ticks = [
                    tick for tick in tick_list
                    if start_time <= tick['timestamp'] <= end_time
                ]

                if filtered_ticks:
                    return pd.DataFrame(filtered_ticks)

            # 从miniQMT获取
            tick_data = self._xtdata.get_market_data(
                stock_list=[symbol],
                period='tick',
                start_time=start_time,
                end_time=end_time
            )

            return tick_data if tick_data is not None else pd.DataFrame()

        except Exception as e:
            self.logger.error(f"获取tick数据失败: {symbol}, {e}")
            return pd.DataFrame()

    def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_time: datetime = None,
        end_time: datetime = None,
        count: int = 100
    ) -> pd.DataFrame:
        """获取K线数据"""
        try:
            if not self._xtdata:
                return pd.DataFrame()

            # 从缓存获取
            cache_key = f"{symbol}_{period}"
            if cache_key in self._kline_cache:
                return self._kline_cache[cache_key]

            # 从miniQMT获取
            kline_data = self._xtdata.get_market_data(
                stock_list=[symbol],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count
            )

            if kline_data is not None and not kline_data.empty:
                self._kline_cache[cache_key] = kline_data

            return kline_data if kline_data is not None else pd.DataFrame()

        except Exception as e:
            self.logger.error(f"获取K线数据失败: {symbol}, {e}")
            return pd.DataFrame()

    def get_level2_data(self, symbol: str) -> Optional[Dict]:
        """获取Level-2数据"""
        try:
            if not self._xtdata:
                return None

            # 订阅Level-2数据
            self._xtdata.subscribe_quote(
                stock_code=symbol,
                period='tick',
                callback=self._on_level2_update
            )

            # 获取Level-2数据
            level2_data = self._xtdata.get_full_tick([symbol])

            if level2_data and not level2_data.empty:
                return self._convert_level2_to_dict(level2_data, symbol)

            return None

        except Exception as e:
            self.logger.error(f"获取Level-2数据失败: {symbol}, {e}")
            return None

    def _on_quote_update(self, data):
        """实时行情更新回调"""
        try:
            for symbol in data:
                quote_dict = self._convert_quote_to_dict(data[symbol], symbol)
                self._quote_cache[symbol] = quote_dict

                # 触发回调
                if symbol in self._callbacks:
                    for callback in self._callbacks[symbol]:
                        try:
                            callback(quote_dict)
                        except Exception as e:
                            self.logger.error(f"行情回调失败: {e}")

                self._stats['total_quotes'] += 1
                self._stats['last_update_time'] = datetime.now()

        except Exception as e:
            self.logger.error(f"处理行情更新失败: {e}")

    def _on_level2_update(self, data):
        """Level-2数据更新回调"""
        try:
            for symbol in data:
                level2_dict = self._convert_level2_to_dict(data[symbol], symbol)

                # 触发回调
                if symbol in self._callbacks:
                    for callback in self._callbacks[symbol]:
                        try:
                            callback(level2_dict)
                        except Exception as e:
                            self.logger.error(f"Level-2回调失败: {e}")

        except Exception as e:
            self.logger.error(f"处理Level-2更新失败: {e}")

    def _convert_quote_to_dict(self, quote_data, symbol: str) -> Dict:
        """转换行情数据为字典格式"""
        try:
            if isinstance(quote_data, pd.DataFrame):
                if not quote_data.empty:
                    row = quote_data.iloc[-1]
                    return {
                        'symbol': symbol,
                        'last_price': float(row.get('lastPrice', 0)),
                        'volume': float(row.get('volume', 0)),
                        'amount': float(row.get('amount', 0)),
                        'bid_price': float(row.get('bidPrice', 0)),
                        'ask_price': float(row.get('askPrice', 0)),
                        'bid_volume': float(row.get('bidVol', 0)),
                        'ask_volume': float(row.get('askVol', 0)),
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'pre_close': float(row.get('preClose', 0)),
                        'timestamp': datetime.now()
                    }
            elif isinstance(quote_data, dict):
                return {
                    'symbol': symbol,
                    'last_price': float(quote_data.get('lastPrice', 0)),
                    'volume': float(quote_data.get('volume', 0)),
                    'amount': float(quote_data.get('amount', 0)),
                    'bid_price': float(quote_data.get('bidPrice', 0)),
                    'ask_price': float(quote_data.get('askPrice', 0)),
                    'bid_volume': float(quote_data.get('bidVol', 0)),
                    'ask_volume': float(quote_data.get('askVol', 0)),
                    'open': float(quote_data.get('open', 0)),
                    'high': float(quote_data.get('high', 0)),
                    'low': float(quote_data.get('low', 0)),
                    'pre_close': float(quote_data.get('preClose', 0)),
                    'timestamp': datetime.now()
                }

            return {}

        except Exception as e:
            self.logger.error(f"转换行情数据失败: {e}")
            return {}

    def _convert_level2_to_dict(self, level2_data, symbol: str) -> Dict:
        """转换Level-2数据为字典格式"""
        try:
            if isinstance(level2_data, pd.DataFrame):
                if not level2_data.empty:
                    row = level2_data.iloc[-1]
                    return {
                        'symbol': symbol,
                        'bids': [
                            {'price': float(row.get(f'bidPrice{i}', 0)), 'volume': float(row.get(f'bidVol{i}', 0))}
                            for i in range(1, 6)
                        ],
                        'asks': [
                            {'price': float(row.get(f'askPrice{i}', 0)), 'volume': float(row.get(f'askVol{i}', 0))}
                            for i in range(1, 6)
                        ],
                        'timestamp': datetime.now()
                    }

            return {}

        except Exception as e:
            self.logger.error(f"转换Level-2数据失败: {e}")
            return {}

    def _start_push_thread(self):
        """启动数据推送线程"""
        if self._push_running:
            return

        self._push_running = True
        self._push_thread = threading.Thread(target=self._push_loop, daemon=True)
        self._push_thread.start()
        self.logger.info("数据推送线程已启动")

    def _push_loop(self):
        """数据推送循环"""
        while self._push_running:
            try:
                time.sleep(self._push_interval)

                # 定期清理缓存
                self._cleanup_cache()

            except Exception as e:
                self.logger.error(f"数据推送循环异常: {e}")

    def _cleanup_cache(self):
        """清理过期缓存"""
        try:
            now = datetime.now()
            ttl = timedelta(seconds=self.config.cache_ttl)

            # 清理行情缓存
            expired_quotes = [
                symbol for symbol, data in self._quote_cache.items()
                if now - data.get('timestamp', now) > ttl
            ]
            for symbol in expired_quotes:
                del self._quote_cache[symbol]

            # 清理tick缓存
            for symbol in self._tick_cache:
                self._tick_cache[symbol] = [
                    tick for tick in self._tick_cache[symbol]
                    if now - tick.get('timestamp', now) <= ttl
                ]

        except Exception as e:
            self.logger.error(f"清理缓存失败: {e}")

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return self._plugin_info

    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        return ConnectionInfo(
            is_connected=self._connected,
            connection_time=self._last_connection_time,
            last_activity=self._stats.get('last_update_time'),
            connection_params={
                'ip': self.config.ip,
                'port': self.config.port,
                'session_id': self.config.session_id
            }
        )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        return self._internal_get_asset_list(asset_type, market)

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """获取K线数据"""
        return self._internal_get_kdata(symbol, freq, start_date, end_date, count)

    def get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        return self._internal_get_real_time_quotes(symbols)

    def get_real_time_data(self, symbols: Union[str, List[str]]) -> pd.DataFrame:
        """
        获取实时数据（统一接口，兼容 EnhancedRealtimeDataManager）

        Args:
            symbols: 股票代码或代码列表

        Returns:
            pd.DataFrame: 实时行情数据，symbol 作为普通列而非索引
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        quotes = self._internal_get_real_time_quotes(symbols)
        if not quotes:
            return pd.DataFrame()

        df = pd.DataFrame(quotes)
        if df.empty:
            return df

        if 'symbol' in df.columns:
            df.reset_index(drop=True, inplace=True)
        return df

    def get_version(self) -> str:
        """获取插件版本"""
        return self._plugin_info.version

    def get_description(self) -> str:
        """获取插件描述"""
        return self._plugin_info.description

    def get_author(self) -> str:
        """获取插件作者"""
        return self._plugin_info.author

    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力"""
        return {
            'realtime': True,
            'historical': True,
            'level2': True,
            'tick': True,
            'multi_market': True,
            'subscription': True,
            'caching': self.config.enable_cache
        }

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return self.config.supported_asset_types

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return self.config.supported_data_types

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            if not self._connected:
                return HealthCheckResult(
                    is_healthy=False,
                    message="未连接到miniQMT",
                    last_check_time=datetime.now()
                )

            # 检查连接状态
            if self._xtdata:
                test_symbol = "000001.SZ"  # 平安银行
                quote = self.get_realtime_quote(test_symbol)

                if quote:
                    return HealthCheckResult(
                        is_healthy=True,
                        message="miniQMT连接正常",
                        last_check_time=datetime.now(),
                        details={
                            'total_quotes': self._stats['total_quotes'],
                            'last_update': self._stats['last_update_time'].isoformat() if self._stats['last_update_time'] else None
                        }
                    )

            return HealthCheckResult(
                is_healthy=False,
                message="miniQMT连接异常",
                last_check_time=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查失败: {str(e)}",
                last_check_time=datetime.now()
            )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'connected': self._connected,
            'subscriptions': len(self._subscriptions),
            'callbacks': len(self._callbacks),
            'stats': self._stats.copy()
        }

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return self._plugin_info

    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """初始化插件"""
        try:
            self.logger.info("初始化miniQMT插件...")

            # 检查 xtquant 库是否可用
            if not XTQUANT_AVAILABLE:
                self.logger.error("xtquant (miniQMT) 未安装，请先安装: pip install xtquant")
                return False

            # 合并配置
            if config:
                if 'ip' in config:
                    self.config.ip = config['ip']
                if 'port' in config:
                    self.config.port = config['port']
                if 'session_id' in config:
                    self.config.session_id = config['session_id']
                if 'enable_cache' in config:
                    self.config.enable_cache = config['enable_cache']
                if 'cache_ttl' in config:
                    self.config.cache_ttl = config['cache_ttl']

            self.logger.info(f"miniQMT插件配置: {self.config.ip}:{self.config.port}")
            self.logger.info("miniQMT插件初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"miniQMT插件初始化失败: {e}")
            return False

    def _internal_connect(self, **kwargs) -> bool:
        """内部连接实现"""
        try:
            if not XTQUANT_AVAILABLE:
                raise PluginConnectionError(
                    "xtquant (miniQMT) 未安装，请先安装: pip install xtquant"
                )

            self.logger.info(f"正在连接miniQMT: {self.config.ip}:{self.config.port}")

            connect_result = xtdata.connect(
                path=self.config.ip,
                port=self.config.port
            )

            if connect_result != 0:
                raise PluginConnectionError(f"miniQMT连接失败，错误代码: {connect_result}")

            self._xtdata = xtdata
            self._connected = True
            self._is_connected = True
            self._last_connection_time = datetime.now()

            self.logger.info("miniQMT连接成功")
            return True

        except Exception as e:
            self.logger.error(f"miniQMT连接失败: {e}")
            self._connected = False
            self._is_connected = False
            raise PluginConnectionError(f"miniQMT连接失败: {str(e)}")

    def _internal_disconnect(self) -> bool:
        """内部断开连接实现"""
        try:
            if self._push_running:
                self._push_running = False
                if self._push_thread:
                    self._push_thread.join(timeout=5)

            if self._xtdata:
                self._xtdata.disconnect()

            self._connected = False
            self._is_connected = False
            self.logger.info("miniQMT已断开连接")
            return True

        except Exception as e:
            self.logger.error(f"断开miniQMT连接失败: {e}")
            return False

    def _internal_get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """内部获取资产列表实现"""
        try:
            if not self._xtdata:
                return []

            market_code = market or 'SH'
            if market_code in self.config.market_config:
                market_code = self.config.market_config[market_code]

            stock_list = xtdata.get_stock_list_in_sector(market_code)

            if stock_list:
                return [
                    {
                        'symbol': stock,
                        'name': stock,
                        'market': market_code,
                        'asset_type': asset_type.value if hasattr(asset_type, 'value') else str(asset_type)
                    }
                    for stock in stock_list
                ]

            return []

        except Exception as e:
            self.logger.error(f"获取资产列表失败: {asset_type}, {market}, {e}")
            return []

    def _internal_get_kdata(self, symbol: str, freq: str = "D",
                            start_date: str = None, end_date: str = None,
                            count: int = None) -> pd.DataFrame:
        """内部获取K线数据实现"""
        try:
            if not self._xtdata:
                return pd.DataFrame()

            cache_key = f"{symbol}_{freq}"
            if cache_key in self._kline_cache:
                return self._kline_cache[cache_key]

            kline_data = self._xtdata.get_market_data(
                stock_list=[symbol],
                period=freq,
                start_time=start_date,
                end_time=end_date,
                count=count
            )

            if kline_data is not None and not kline_data.empty:
                self._kline_cache[cache_key] = kline_data

            return kline_data if kline_data is not None else pd.DataFrame()

        except Exception as e:
            self.logger.error(f"获取K线数据失败: {symbol}, {e}")
            return pd.DataFrame()

    def _internal_get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """内部获取实时行情实现"""
        try:
            if not self._xtdata:
                return []

            quotes = []
            for symbol in symbols:
                quote = self.get_realtime_quote(symbol)
                if quote:
                    quotes.append(quote)

            return quotes

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {e}")
            return []
