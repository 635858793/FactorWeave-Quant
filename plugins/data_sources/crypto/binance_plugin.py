"""
币安加密货币数据源插件（生产级）

提供币安交易所数字货币数据获取功能，支持：
- 主流数字货币实时价格
- 历史K线数据（多周期）
- 市场深度数据
- 交易对信息
- 24小时统计数据
- WebSocket实时推送

技术特性：
- 异步初始化（快速启动）
- HTTP连接池（高并发）
- WebSocket连接池（实时推送）
- 智能限流（1200次/分钟）
- 自动重试（指数退避）
- LRU缓存（提升性能）
- 健康检查（自动熔断）

作者: FactorWeave-Quant 开发团队
版本: 2.0.0 (生产级)
日期: 2025-10-17
"""

import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

# 导入模板基类
import sys
from pathlib import Path

# 使用相对导入templates（避免sys.path操作）
from plugins.data_sources.templates.http_api_plugin_template import HTTPAPIPluginTemplate
from plugins.data_sources.templates.websocket_plugin_template import WebSocketPluginTemplate
from core.plugin_types import PluginType, AssetType, DataType

logger = logger.bind(module=__name__)


class BinancePlugin(HTTPAPIPluginTemplate):
    """
    币安加密货币数据源插件（生产级）

    继承自HTTPAPIPluginTemplate，获得：
    - 异步初始化
    - 连接池管理
    - 智能重试
    - 限流控制
    - 缓存优化
    - 健康检查
    """

    def __init__(self):
        """初始化币安插件"""
        # 插件基本信息（在super().__init__()之前定义，因为父类会调用_get_default_config）
        self.plugin_id = "data_sources.crypto.binance_plugin"
        self.name = "Binance加密货币数据源"
        self.version = "2.0.0"
        self.description = "提供币安交易所数字货币实时和历史数据，生产级实现"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_CRYPTO

        # 币安特定配置（在super().__init__()之前定义）
        self.BINANCE_CONFIG = {
            # API端点
            'base_url': 'https://api.binance.com',
            'ws_url': 'wss://stream.binance.com:9443/ws',

            # API路径
            'api_endpoints': {
                'ping': '/api/v3/ping',
                'time': '/api/v3/time',
                'exchange_info': '/api/v3/exchangeInfo',
                'klines': '/api/v3/klines',
                'ticker_24hr': '/api/v3/ticker/24hr',
                'ticker_price': '/api/v3/ticker/price',
                'depth': '/api/v3/depth',
                'trades': '/api/v3/trades',
                'agg_trades': '/api/v3/aggTrades',
            },

            # 周期映射
            'interval_mapping': {
                '1min': '1m', '3min': '3m', '5min': '5m', '15min': '15m', '30min': '30m',
                '1hour': '1h', '2hour': '2h', '4hour': '4h', '6hour': '6h', '8hour': '8h', '12hour': '12h',
                'daily': '1d', 'D': '1d',
                'weekly': '1w', 'W': '1w',
                'monthly': '1M', 'M': '1M',
                # R275 补齐系统标准周期键（UDM/Period 传值），防静默回退日线
                '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '60m',
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '60m': '60m',
                '1H': '1h', '1h': '1h'
            },

            # 限流配置（币安：1200次/分钟 = 20次/秒）
            'rate_limit_per_minute': 1200,
            'rate_limit_per_second': 20,

            # 重试配置
            'max_retries': 3,
            'retry_backoff_factor': 0.5,

            # 超时配置
            'timeout': 30,

            # 连接池配置
            'pool_connections': 10,
            'pool_maxsize': 10,

            # 缓存配置
            'cache_enabled': True,
            'cache_ttl': 60,  # 缓存1分钟

            # API密钥（可选，用于私有API）
            'api_key': '',
            'api_secret': '',
        }

        # 调用父类初始化（在BINANCE_CONFIG定义之后）
        super().__init__()

        # 合并配置
        self.DEFAULT_CONFIG.update(self.BINANCE_CONFIG)

        # 主要交易对
        self.major_symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
            'DOGEUSDT', 'DOTUSDT', 'UNIUSDT', 'LTCUSDT', 'LINKUSDT',
            'BCHUSDT', 'XLMUSDT', 'VETUSDT', 'ETCUSDT', 'THETAUSDT'
        ]

        # 交易对信息缓存
        self._exchange_info = None
        self._exchange_info_time = 0
        self._exchange_info_ttl = 3600  # 交易所信息缓存1小时

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        config = super()._get_default_config()
        config.update(self.BINANCE_CONFIG)
        return config

    def _get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        headers = {
            'User-Agent': f'FactorWeave-Quant/{self.version}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # 如果有API密钥，添加到headers
        api_key = self.config.get('api_key', '')
        if api_key:
            headers['X-MBX-APIKEY'] = api_key

        return headers

    def _test_connection(self) -> bool:
        """测试连接"""
        try:
            # Ping测试
            ping_endpoint = self.config['api_endpoints']['ping']
            ping_response = self._request('GET', ping_endpoint, use_cache=False)

            if ping_response is None:
                return False

            # 获取服务器时间验证
            time_endpoint = self.config['api_endpoints']['time']
            time_response = self._request('GET', time_endpoint, use_cache=False)

            if time_response and 'serverTime' in time_response:
                server_time = time_response['serverTime']
                local_time = int(time.time() * 1000)
                time_diff = abs(server_time - local_time)

                # 时间差应小于5秒
                if time_diff > 5000:
                    self.logger.warning(f"服务器时间差异较大: {time_diff}ms")

                self.logger.info(f"币安API连接成功，服务器时间: {server_time}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"测试连接失败: {e}")
            return False

    def _sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        币安API请求签名

        币安签名规则：
        1. 所有参数按字母顺序排序
        2. 拼接成query string
        3. 使用HMAC-SHA256签名
        4. 添加timestamp和signature参数
        """
        if not self.config.get('api_secret'):
            return params or {}

        # 添加时间戳
        timestamp = int(time.time() * 1000)
        params = params or {}
        params['timestamp'] = timestamp

        # 构建签名字符串
        query_string = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))

        # 生成签名
        signature = self._generate_signature(query_string, self.config['api_secret'])
        params['signature'] = signature

        return params

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return [AssetType.CRYPTO]

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return [
            DataType.HISTORICAL_KLINE,
            DataType.REAL_TIME_QUOTE,
            DataType.MARKET_DEPTH,
            DataType.TRADE_TICK
        ]

    def get_exchange_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取交易所信息

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            Dict: 交易所信息
        """
        try:
            # 检查缓存
            current_time = time.time()
            if not force_refresh and self._exchange_info:
                if current_time - self._exchange_info_time < self._exchange_info_ttl:
                    return self._exchange_info

            # 获取交易所信息
            endpoint = self.config['api_endpoints']['exchange_info']
            response = self._request('GET', endpoint)

            if response:
                self._exchange_info = response
                self._exchange_info_time = current_time
                self.logger.info("获取币安交易所信息成功")
                return response

            return {}

        except Exception as e:
            self.logger.error(f"获取交易所信息失败: {e}")
            return {}

    def get_symbol_list(self) -> pd.DataFrame:
        """
        获取交易对列表

        Returns:
            pd.DataFrame: 交易对列表
        """
        try:
            exchange_info = self.get_exchange_info()

            if not exchange_info or 'symbols' not in exchange_info:
                return pd.DataFrame()

            symbols_data = [
                {
                    'symbol': symbol_info['symbol'],
                    'base_asset': symbol_info['baseAsset'],
                    'quote_asset': symbol_info['quoteAsset'],
                    'status': symbol_info['status'],
                    'base_precision': symbol_info.get('baseAssetPrecision', 8),
                    'quote_precision': symbol_info.get('quotePrecision', 8),
                    'permissions': ','.join(symbol_info.get('permissions', [])),
                }
                for symbol_info in exchange_info['symbols']
                if symbol_info['status'] == 'TRADING'
            ]

            df = pd.DataFrame(symbols_data)
            self.logger.info(f"获取币安交易对列表成功，共 {len(df)} 个交易对")
            return df

        except Exception as e:
            self.logger.error(f"获取交易对列表失败: {e}")
            return pd.DataFrame()

    def get_kdata(
        self,
        symbol: str,
        interval: str = 'daily',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易对（如'BTCUSDT'）
            interval: 周期（daily, 1hour, 5min等）
            start_date: 开始日期
            end_date: 结束日期
            limit: 数据条数（最大1000）

        Returns:
            pd.DataFrame: K线数据
        """
        try:
            # 转换周期
            interval_mapping = self.config.get('interval_mapping', {})
            binance_interval = interval_mapping.get(interval, '1d')

            # 构建请求参数
            endpoint = self.config['api_endpoints']['klines']
            params = {
                'symbol': symbol.upper(),
                'interval': binance_interval,
                'limit': min(limit, 1000)  # 币安限制最大1000
            }

            # 添加时间范围
            if start_date:
                params['startTime'] = int(start_date.timestamp() * 1000)
            if end_date:
                params['endTime'] = int(end_date.timestamp() * 1000)

            # 发送请求
            response = self._request('GET', endpoint, params=params)

            if not response:
                return pd.DataFrame()

            # 转换为DataFrame
            df = pd.DataFrame(response, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'count', 'taker_buy_volume',
                'taker_buy_quote_volume', 'ignore'
            ])

            # 数据类型转换
            df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume']

            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 设置索引
            df = df.set_index('datetime')

            # 选择主要列
            df = df[['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'count']]

            self.logger.info(f"获取 {symbol} K线数据成功，共 {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"获取K线数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_24hr_ticker(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        获取24小时价格变动统计

        Args:
            symbol: 交易对（可选，不指定则返回所有）

        Returns:
            pd.DataFrame: 24小时统计数据
        """
        try:
            endpoint = self.config['api_endpoints']['ticker_24hr']
            params = {}

            if symbol:
                params['symbol'] = symbol.upper()

            response = self._request('GET', endpoint, params=params)

            if not response:
                return pd.DataFrame()

            # 确保数据是列表格式
            if isinstance(response, dict):
                response = [response]

            df = pd.DataFrame(response)

            if df.empty:
                return df

            # 选择主要列并重命名
            columns_mapping = {
                'symbol': 'symbol',
                'lastPrice': 'price',
                'priceChangePercent': 'pct_change',
                'priceChange': 'change',
                'volume': 'volume',
                'quoteVolume': 'quote_volume',
                'highPrice': 'high_24h',
                'lowPrice': 'low_24h',
                'openPrice': 'open_24h',
                'count': 'trade_count'
            }

            available_cols = {k: v for k, v in columns_mapping.items() if k in df.columns}
            df = df[list(available_cols.keys())].rename(columns=available_cols)

            # 数据类型转换
            numeric_cols = ['price', 'pct_change', 'change', 'volume', 'quote_volume',
                            'high_24h', 'low_24h', 'open_24h']

            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            self.logger.info(f"获取24小时统计数据成功，共 {len(df)} 个交易对")
            return df

        except Exception as e:
            self.logger.error(f"获取24小时统计数据失败: {e}")
            return pd.DataFrame()

    def get_real_time_price(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """
        获取实时价格

        Args:
            symbols: 交易对列表（可选）

        Returns:
            pd.DataFrame: 实时价格数据
        """
        try:
            endpoint = self.config['api_endpoints']['ticker_price']
            params = {}

            if symbols:
                if len(symbols) == 1:
                    params['symbol'] = symbols[0].upper()
                else:
                    # 对于多个交易对，使用24hr ticker
                    return self.get_24hr_ticker()

            response = self._request('GET', endpoint, params=params)

            if not response:
                return pd.DataFrame()

            # 确保数据是列表格式
            if isinstance(response, dict):
                response = [response]

            df = pd.DataFrame(response)

            if df.empty:
                return df

            # 重命名列
            if 'price' in df.columns:
                df['price'] = pd.to_numeric(df['price'], errors='coerce')

            # 如果指定了交易对，进行筛选
            if symbols and len(symbols) > 1:
                upper_symbols = [s.upper() for s in symbols]
                df = df[df['symbol'].isin(upper_symbols)]

            self.logger.info(f"获取实时价格成功，共 {len(df)} 个交易对")
            return df

        except Exception as e:
            self.logger.error(f"获取实时价格失败: {e}")
            return pd.DataFrame()

    def get_market_depth(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        获取市场深度

        Args:
            symbol: 交易对
            limit: 深度档位（5, 10, 20, 50, 100, 500, 1000, 5000）

        Returns:
            Dict: 市场深度数据
        """
        try:
            endpoint = self.config['api_endpoints']['depth']
            params = {
                'symbol': symbol.upper(),
                'limit': min(limit, 5000)  # 币安限制
            }

            response = self._request('GET', endpoint, params=params)

            if not response:
                return {}

            # 转换深度数据
            depth_data = {
                'symbol': symbol,
                'bids': [[float(price), float(qty)] for price, qty in response.get('bids', [])],
                'asks': [[float(price), float(qty)] for price, qty in response.get('asks', [])],
                'timestamp': response.get('lastUpdateId', 0)
            }

            self.logger.info(f"获取 {symbol} 市场深度成功")
            return depth_data

        except Exception as e:
            self.logger.error(f"获取市场深度失败 {symbol}: {e}")
            return {}

    def get_recent_trades(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        """
        获取最近成交

        Args:
            symbol: 交易对
            limit: 数量（最大1000）

        Returns:
            pd.DataFrame: 成交数据
        """
        try:
            endpoint = self.config['api_endpoints']['trades']
            params = {
                'symbol': symbol.upper(),
                'limit': min(limit, 1000)
            }

            response = self._request('GET', endpoint, params=params)

            if not response:
                return pd.DataFrame()

            df = pd.DataFrame(response)

            if df.empty:
                return df

            # 数据类型转换
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce')

            self.logger.info(f"获取 {symbol} 最近成交成功，共 {len(df)} 条")
            return df

        except Exception as e:
            self.logger.error(f"获取最近成交失败 {symbol}: {e}")
            return pd.DataFrame()

    def fetch_data(
        self,
        symbol: str,
        data_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> Any:
        """
        通用数据获取接口

        Args:
            symbol: 交易对
            data_type: 数据类型（kline, realtime, depth, trades等）
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            Any: 数据（DataFrame或Dict）
        """
        try:
            if data_type in ['kline', 'historical_kline']:
                return self.get_kdata(
                    symbol=symbol,
                    interval=kwargs.get('interval', 'daily'),
                    start_date=start_date,
                    end_date=end_date,
                    limit=kwargs.get('limit', 500)
                )

            elif data_type in ['realtime', 'real_time_quote']:
                symbols = kwargs.get('symbols', [symbol])
                return self.get_real_time_price(symbols)

            elif data_type == '24hr_ticker':
                return self.get_24hr_ticker(symbol)

            elif data_type in ['depth', 'market_depth']:
                return self.get_market_depth(symbol, kwargs.get('limit', 100))

            elif data_type == 'trades':
                return self.get_recent_trades(symbol, kwargs.get('limit', 500))

            elif data_type == 'symbol_list':
                return self.get_symbol_list()

            else:
                raise ValueError(f"不支持的数据类型: {data_type}")

        except Exception as e:
            self.logger.error(f"获取数据失败 {symbol} ({data_type}): {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_requests': self._stats['total_requests'],
            'failed_requests': self._stats['failed_requests'],
            'success_rate': (
                1.0 - (self._stats['failed_requests'] / max(self._stats['total_requests'], 1))
            ),
            'avg_response_time': self._stats['average_response_time'],
            'last_update': self._stats.get('last_request_time'),
            'health_score': self._health_score,
            'major_symbols': self.major_symbols[:10],
            'api_status': 'connected' if self.is_connected() else 'disconnected',
            'plugin_state': self.plugin_state.value if hasattr(self, 'plugin_state') else 'unknown'
        }


# 插件工厂函数
def create_plugin() -> BinancePlugin:
    """创建插件实例"""
    return BinancePlugin()


# 插件元数据
PLUGIN_METADATA = {
    "name": "Binance加密货币数据源",
    "version": "2.0.0",
    "description": "提供币安交易所数字货币实时和历史数据，生产级实现",
    "author": "FactorWeave-Quant 开发团队",
    "plugin_type": "data_source_crypto",
    "asset_types": ["crypto"],
    "data_types": ["historical_kline", "real_time_quote", "market_depth", "trade_tick"],
    "exchanges": ["binance"],
    "production_ready": True,
    "features": [
        "async_initialization",
        "connection_pool",
        "rate_limiting",
        "intelligent_retry",
        "lru_cache",
        "health_check",
        "circuit_breaker"
    ]
}
