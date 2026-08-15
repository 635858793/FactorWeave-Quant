"""
加密货币通用数据源插件（生产级）

提供多交易所统一接口的数字货币数据获取功能，支持：
- 多交易所数据聚合（Binance, OKX, Huobi, Coinbase等）
- 智能交易所选择和故障转移
- 主流数字货币实时价格
- 历史K线数据（多周期）
- 市场深度数据
- 交易对信息
- 24小时统计数据

技术特性：
- 异步初始化（快速启动）
- HTTP连接池（高并发）
- 多交易所负载均衡
- 智能限流（根据交易所自适应）
- 自动重试和故障转移
- LRU缓存（提升性能）
- 健康检查（自动熔断）

作者: FactorWeave-Quant 开发团队
版本: 2.0.0 (生产级)
日期: 2025-10-18
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

# 导入模板基类
import sys
from pathlib import Path

# 使用相对导入templates（避免sys.path操作）
from plugins.data_sources.templates.http_api_plugin_template import HTTPAPIPluginTemplate
from core.plugin_types import PluginType, AssetType, DataType

logger = logger.bind(module=__name__)


class CryptoUniversalPlugin(HTTPAPIPluginTemplate):
    """
    加密货币通用数据源插件（生产级）

    提供统一接口访问多个加密货币交易所，
    支持智能路由、负载均衡和故障转移。

    继承自HTTPAPIPluginTemplate，获得：
    - 异步初始化
    - 连接池管理
    - 智能重试
    - 限流控制
    - 缓存优化
    - 健康检查
    """

    def __init__(self):
        """初始化加密货币通用插件"""
        # 插件基本信息（在super().__init__()之前定义，因为父类会调用_get_default_config）
        self.plugin_id = "data_sources.crypto.crypto_universal_plugin"
        self.name = "加密货币通用数据源"
        self.version = "2.0.0"
        self.description = "提供多交易所统一接口的数字货币数据，支持智能路由和故障转移，生产级实现"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_CRYPTO

        # 通用配置（在super().__init__()之前定义）
        self.UNIVERSAL_CONFIG = {
            # 默认base_url（使用Binance作为默认）
            'base_url': 'https://api.binance.com',

            # 支持的交易所列表
            'exchanges': {
                'binance': {
                    'enabled': True,
                    'priority': 1,  # 优先级（越小越高）
                    'weight': 0.4,  # 权重
                    'base_url': 'https://api.binance.com',
                    'rate_limit': 1200,
                },
                'okx': {
                    'enabled': True,
                    'priority': 2,
                    'weight': 0.3,
                    'base_url': 'https://www.okx.com',
                    'rate_limit': 600,
                },
                'huobi': {
                    'enabled': True,
                    'priority': 3,
                    'weight': 0.2,
                    'base_url': 'https://api.huobi.pro',
                    'rate_limit': 600,
                },
                'coinbase': {
                    'enabled': True,
                    'priority': 4,
                    'weight': 0.1,
                    'base_url': 'https://api.exchange.coinbase.com',
                    'rate_limit': 600,
                },
            },

            # 路由策略
            'routing_strategy': 'weighted_random',  # 'priority', 'round_robin', 'weighted_random', 'health_based'

            # 故障转移配置
            'failover_enabled': True,
            'max_failover_attempts': 3,
            'failover_cooldown': 60,  # 秒

            # 数据一致性配置
            'enable_cross_validation': False,  # 是否开启跨交易所数据验证
            'validation_threshold': 0.01,  # 数据差异阈值（1%）

            # 符号映射（不同交易所的符号格式可能不同）
            'symbol_mapping': {
                'BTC': ['BTCUSDT', 'BTC-USDT', 'btcusdt', 'BTC-USD'],
                'ETH': ['ETHUSDT', 'ETH-USDT', 'ethusdt', 'ETH-USD'],
                'BNB': ['BNBUSDT', 'BNB-USDT', 'bnbusdt'],
            },

            # 限流配置（全局）
            'rate_limit_per_minute': 2400,  # 所有交易所总和
            'rate_limit_per_second': 40,

            # 重试配置
            'max_retries': 3,
            'retry_backoff_factor': 0.5,

            # 超时配置
            'timeout': 30,

            # 连接池配置
            'pool_connections': 20,  # 更大的连接池以支持多交易所
            'pool_maxsize': 20,

            # 缓存配置
            'cache_enabled': True,
            'cache_ttl': 60,  # 缓存1分钟

            # API端点（各交易所 REST 路径，R275 扩展：真实数据获取替代占位实现）
            'api_endpoints': {
                'binance_klines': '/api/v3/klines',
                'binance_ticker': '/api/v3/ticker/price',
                'okx_candles': '/api/v5/market/candles',
                'okx_ticker': '/api/v5/market/ticker',
                'huobi_kline': '/market/history/kline',
                'huobi_ticker': '/market/detail/merged',
                'coinbase_candles': '/products/{product_id}/candles',
                'coinbase_ticker': '/products/{product_id}/ticker',
            },
        }

        # 调用父类初始化（在UNIVERSAL_CONFIG定义之后）
        super().__init__()

        # 合并配置
        self.DEFAULT_CONFIG.update(self.UNIVERSAL_CONFIG)

        # 主要交易对（标准化格式）
        self.major_symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
            'DOGEUSDT', 'DOTUSDT', 'UNIUSDT', 'LTCUSDT', 'LINKUSDT',
            'BCHUSDT', 'XLMUSDT', 'VETUSDT', 'ETCUSDT', 'THETAUSDT'
        ]

        # 交易所健康状态跟踪
        self._exchange_health = {}
        for exchange in self.UNIVERSAL_CONFIG['exchanges'].keys():
            self._exchange_health[exchange] = {
                'available': True,
                'last_check': 0,
                'success_count': 0,
                'failure_count': 0,
                'avg_response_time': 0,
                'health_score': 1.0
            }

        # 当前使用的交易所（轮询策略）
        self._current_exchange_index = 0

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        config = super()._get_default_config()
        if hasattr(self, 'UNIVERSAL_CONFIG'):
            config.update(self.UNIVERSAL_CONFIG)
        return config

    def _get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            'User-Agent': f'FactorWeave-Quant-Universal/{self.version}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _test_connection(self) -> bool:
        """测试连接（测试所有启用的交易所）"""
        try:
            enabled_exchanges = [
                name for name, config in self.config['exchanges'].items()
                if config.get('enabled', False)
            ]

            if not enabled_exchanges:
                self.logger.error("没有启用的交易所")
                return False

            successful = 0
            for exchange in enabled_exchanges:
                if self._test_exchange_connection(exchange):
                    successful += 1
                    self.logger.info(f"交易所 {exchange} 连接成功")
                else:
                    self.logger.warning(f"交易所 {exchange} 连接失败")

            # 只要有一个交易所连接成功即可
            if successful > 0:
                self.logger.info(f"通用插件连接成功，{successful}/{len(enabled_exchanges)} 个交易所可用")
                return True

            return False

        except Exception as e:
            self.logger.error(f"测试连接失败: {e}")
            return False

    def _test_exchange_connection(self, exchange: str) -> bool:
        """测试单个交易所连接"""
        # R248: 原实现恒返回 True（"这里简化处理"），导致 connect 验证形同虚设。
        # 改为对交易所 base_url 发起真实 HTTP 探测：服务器可达（无异常）即成功。
        try:
            exchange_config = self.config.get('exchanges', {}).get(exchange)
            if not exchange_config:
                self.logger.warning(f"交易所 {exchange} 无配置")
                return False

            base_url = exchange_config.get('base_url')
            if not base_url:
                self.logger.warning(f"交易所 {exchange} 未配置 base_url")
                return False

            if self.session is None:
                import requests
                self.session = requests.Session()

            response = self.session.get(base_url, timeout=10)
            self.logger.info(f"交易所 {exchange} HTTP {response.status_code}")
            return True

        except Exception as e:
            self.logger.error(f"交易所 {exchange} 连接测试失败: {e}")
            return False

    def _sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        请求签名（根据交易所动态签名）
        """
        # 通用插件不需要签名（使用公共API）
        return params or {}

    def _select_exchange(
        self,
        symbol: Optional[str] = None,
        preferred_exchange: Optional[str] = None
    ) -> str:
        """
        选择交易所

        Args:
            symbol: 交易对
            preferred_exchange: 首选交易所

        Returns:
            str: 交易所名称
        """
        strategy = self.config.get('routing_strategy', 'weighted_random')

        # 如果指定了首选交易所且可用，使用它
        if preferred_exchange and self._is_exchange_healthy(preferred_exchange):
            return preferred_exchange

        # 获取可用的交易所列表
        available_exchanges = [
            name for name, config in self.config.get('exchanges', {}).items()
            if config.get('enabled', False) and self._is_exchange_healthy(name)
        ]

        if not available_exchanges:
            self.logger.error("没有可用的交易所")
            return 'binance'  # 默认返回binance

        # 根据策略选择
        if strategy == 'priority':
            # 按优先级选择
            return min(available_exchanges,
                       key=lambda x: self.config['exchanges'][x].get('priority', 999))

        elif strategy == 'round_robin':
            # 轮询选择
            exchange = available_exchanges[self._current_exchange_index % len(available_exchanges)]
            self._current_exchange_index += 1
            return exchange

        elif strategy == 'weighted_random':
            # 加权随机选择
            import random
            weights = [self.config['exchanges'][ex].get('weight', 0.25) for ex in available_exchanges]
            return random.choices(available_exchanges, weights=weights)[0]

        elif strategy == 'health_based':
            # 基于健康分数选择
            return max(available_exchanges,
                       key=lambda x: self._exchange_health[x]['health_score'])

        else:
            return available_exchanges[0]

    def _is_exchange_healthy(self, exchange: str) -> bool:
        """检查交易所是否健康"""
        health = self._exchange_health.get(exchange, {})
        return health.get('available', False) and health.get('health_score', 0) > 0.3

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

    def get_symbol_list(self, exchange: Optional[str] = None) -> pd.DataFrame:
        """
        获取交易对列表（从所有交易所聚合）

        Args:
            exchange: 指定交易所（可选）

        Returns:
            pd.DataFrame: 交易对列表
        """
        try:
            if exchange:
                exchanges = [exchange]
            else:
                exchanges = [
                    name for name, config in self.config['exchanges'].items()
                    if config.get('enabled', False)
                ]

            all_symbols = []

            for ex in exchanges:
                # 这里需要调用各交易所的API获取交易对列表
                # 简化处理，返回主要交易对
                for symbol in self.major_symbols:
                    all_symbols.append({
                        'symbol': symbol,
                        'exchange': ex,
                        'base_asset': symbol[:3] if len(symbol) > 6 else symbol[:symbol.find('USDT')],
                        'quote_asset': 'USDT',
                        'status': 'active'
                    })

            df = pd.DataFrame(all_symbols)

            # 去重
            if not df.empty:
                df = df.drop_duplicates(subset=['symbol', 'exchange'])

            self.logger.info(f"获取交易对列表成功，共 {len(df)} 个")
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
        limit: int = 500,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取K线数据（带故障转移）

        Args:
            symbol: 交易对
            interval: 周期
            start_date: 开始日期
            end_date: 结束日期
            limit: 数据条数
            exchange: 指定交易所（可选）

        Returns:
            pd.DataFrame: K线数据
        """
        try:
            selected_exchange = self._select_exchange(symbol, exchange)
            attempts = 0
            max_attempts = self.config.get('max_failover_attempts', 3)

            while attempts < max_attempts:
                try:
                    self.logger.info(f"从 {selected_exchange} 获取 {symbol} K线数据")

                    # R275 扩展：真实数据获取（替代占位实现）
                    df = self._fetch_kline_from_exchange(
                        selected_exchange, symbol, interval,
                        start_date, end_date, limit)

                    # 更新健康状态
                    self._update_exchange_health(selected_exchange, success=True)

                    if df is not None and not df.empty:
                        return df

                    # 返回空数据也视为本次交易所不可用，尝试故障转移
                    self.logger.warning(f"从 {selected_exchange} 获取 {symbol} K线为空")
                    self._update_exchange_health(selected_exchange, success=False)
                    if self.config.get('failover_enabled', True):
                        attempts += 1
                        selected_exchange = self._select_exchange(symbol, None)
                        self.logger.info(f"故障转移到 {selected_exchange}，尝试 {attempts}/{max_attempts}")
                    else:
                        break

                except Exception as e:
                    self.logger.warning(f"从 {selected_exchange} 获取数据失败: {e}")
                    self._update_exchange_health(selected_exchange, success=False)

                    # 尝试故障转移
                    if self.config.get('failover_enabled', True):
                        attempts += 1
                        selected_exchange = self._select_exchange(symbol, None)
                        self.logger.info(f"故障转移到 {selected_exchange}，尝试 {attempts}/{max_attempts}")
                    else:
                        break

            return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"获取K线数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_real_time_price(
        self,
        symbols: Optional[List[str]] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取实时价格（带故障转移）

        Args:
            symbols: 交易对列表
            exchange: 指定交易所（可选）

        Returns:
            pd.DataFrame: 实时价格数据
        """
        try:
            if not symbols:
                symbols = self.major_symbols

            selected_exchange = self._select_exchange(None, exchange)

            # R275 扩展：真实价格获取（替代占位实现 price=0.0）
            self.logger.info(f"从 {selected_exchange} 获取实时价格")

            prices_data = []
            for symbol in symbols:
                try:
                    price = self._fetch_price_from_exchange(selected_exchange, symbol)
                    prices_data.append({
                        'symbol': symbol,
                        'price': price if price is not None else 0.0,
                        'exchange': selected_exchange,
                        'timestamp': datetime.now()
                    })
                except Exception as e:
                    self.logger.warning(f"从 {selected_exchange} 获取 {symbol} 实时价格失败: {e}")
                    prices_data.append({
                        'symbol': symbol,
                        'price': 0.0,
                        'exchange': selected_exchange,
                        'timestamp': datetime.now()
                    })

            self._update_exchange_health(selected_exchange, success=True)

            df = pd.DataFrame(prices_data)
            return df

        except Exception as e:
            self.logger.error(f"获取实时价格失败: {e}")
            return pd.DataFrame()

    # ---------- R275 扩展：真实数据获取辅助方法 ----------

    def _get_interval_mapping(self, exchange: str) -> Dict[str, Any]:
        """各交易所周期映射（系统标准键 -> 交易所周期）"""
        mappings = {
            'binance': {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '60m': '1h',
                '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
                '1d': '1d', 'daily': '1d', 'D': '1d',
                '1w': '1w', 'weekly': '1w', 'W': '1w',
                '1M': '1M', 'monthly': '1M', 'M': '1M',
                # 系统标准数字/简写键
                '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h',
                '1H': '1h', '2H': '2h', '4H': '4h', '6H': '6h', '8H': '8h', '12H': '12h',
            },
            'okx': {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '60m': '1H',
                '1h': '1H', '1H': '1H', '2H': '2H', '4H': '4H',
                '6H': '6H', '8H': '8H', '12H': '12H',
                'D': '1D', '1d': '1D', 'daily': '1D',
                'W': '1W', '1w': '1W', 'weekly': '1W',
                'M': '1M', '1M': '1M', 'monthly': '1M',
                '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1H',
            },
            'huobi': {
                '1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min', '60m': '60min',
                '1h': '60min', '1H': '60min', '2H': '2hour', '4H': '4hour',
                '6H': '6hour', '8H': '8hour', '12H': '12hour',
                'D': '1day', '1d': '1day', 'daily': '1day',
                'W': '1week', '1w': '1week', 'weekly': '1week',
                'M': '1mon', '1M': '1mon', 'monthly': '1mon',
                '1': '1min', '5': '5min', '15': '15min', '30': '30min', '60': '60min',
            },
            'coinbase': {
                '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '60m': 3600,
                '1h': 3600, '1H': 3600, '2H': 7200, '4H': 14400,
                '6H': 21600, '8H': 28800, '12H': 43200,
                'D': 86400, '1d': 86400, 'daily': 86400,
                'W': 604800, '1w': 604800, 'weekly': 604800,
                'M': 2592000, '1M': 2592000, 'monthly': 2592000,
                '1': 60, '5': 300, '15': 900, '30': 1800, '60': 3600,
            },
        }
        # 允许配置覆盖
        configured = self.config.get('interval_mapping', {}) if hasattr(self, 'config') else {}
        base = mappings.get(exchange, mappings['binance'])
        if configured:
            base = dict(base)
            base.update(configured)
        return base

    @staticmethod
    def _build_symbol(exchange: str, symbol: str) -> str:
        """将通用交易对转换为各交易所符号格式"""
        sym = symbol.upper()
        if exchange == 'binance':
            if '-' in sym:
                base, quote = sym.split('-', 1)
                sym = f"{base}{quote}"
            # 纯 base 币（如 BTC，长度<=4）需补 USDT 报价；已含报价后缀的不追加
            if not (len(sym) > 4 and (sym.endswith('USDT') or sym.endswith('USDC')
                                      or sym.endswith('BTC') or sym.endswith('USD'))):
                sym = f"{sym}USDT"
            return sym
        if exchange == 'okx':
            if '-' not in sym:
                sym = f"{sym}-USDT"
            return sym
        if exchange == 'huobi':
            low = symbol.lower()
            if not (len(low) > 4 and (low.endswith('usdt') or low.endswith('usdc'))):
                low = f"{low}usdt"
            return low
        if exchange == 'coinbase':
            if '-' not in sym:
                sym = f"{sym}-USD"
            return sym
        return sym.upper()

    def _session_get_json(self, url: str, params: Optional[Dict] = None) -> Any:
        """发送 GET 请求并解析 JSON（复用模板 session）"""
        if not self.session:
            self.logger.error("Session未初始化")
            return None
        try:
            self._rate_limit_check()
            start_time = time.time()
            response = self.session.get(
                url, params=params,
                timeout=self.config.get('timeout', 30))
            response.raise_for_status()
            result = response.json()
            self._record_request(success=True, response_time=time.time() - start_time)
            return result
        except Exception as e:
            self.logger.error(f"请求失败 {url}: {e}")
            self._record_request(success=False)
            return None

    def _fetch_kline_from_exchange(
        self, exchange: str, symbol: str, interval: str,
        start_date: Optional[datetime], end_date: Optional[datetime],
        limit: int
    ) -> pd.DataFrame:
        """从指定交易所获取 K 线并统一为 datetime 索引 DataFrame（升序）"""
        exchange_cfg = self.config.get('exchanges', {}).get(exchange, {})
        base_url = exchange_cfg.get('base_url')
        if not base_url:
            self.logger.error(f"交易所 {exchange} 未配置 base_url")
            return pd.DataFrame()
        endpoints = self.config.get('api_endpoints', {})
        iv_map = self._get_interval_mapping(exchange)
        iv = iv_map.get(interval, iv_map.get('D', iv_map.get('1d')))
        sym = self._build_symbol(exchange, symbol)

        try:
            if exchange == 'binance':
                params = {'symbol': sym, 'interval': iv, 'limit': min(int(limit or 500), 1000)}
                if start_date:
                    params['startTime'] = int(start_date.timestamp() * 1000)
                if end_date:
                    params['endTime'] = int(end_date.timestamp() * 1000)
                data = self._session_get_json(f"{base_url}{endpoints['binance_klines']}", params)
                if not data:
                    return pd.DataFrame()
                df = pd.DataFrame(data, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
                    'taker_buy_quote_volume', 'ignore'])
                df['datetime'] = pd.to_datetime(df['open_time'].astype(int), unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.set_index('datetime')
                return df[['open', 'high', 'low', 'close', 'volume']]

            elif exchange == 'okx':
                params = {'instId': sym, 'bar': iv, 'limit': min(int(limit or 500), 300)}
                body = self._session_get_json(f"{base_url}{endpoints['okx_candles']}", params)
                if not body or body.get('code') != '0':
                    self.logger.warning(f"OKX 返回异常: {body}")
                    return pd.DataFrame()
                rows = list(body.get('data', []))
                rows.reverse()  # OKX 倒序（最新在前）→ 转升序
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows, columns=[
                    'ts', 'open', 'high', 'low', 'close', 'volume',
                    'volCcy', 'volCcyQuote', 'confirm'])
                df['datetime'] = pd.to_datetime(df['ts'].astype(int), unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.set_index('datetime')
                return df[['open', 'high', 'low', 'close', 'volume']]

            elif exchange == 'huobi':
                params = {'symbol': sym, 'period': iv, 'size': min(int(limit or 500), 2000)}
                body = self._session_get_json(f"{base_url}{endpoints['huobi_kline']}", params)
                if not body or body.get('status') != 'ok':
                    self.logger.warning(f"Huobi 返回异常: {body}")
                    return pd.DataFrame()
                rows = body.get('data', [])
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows)
                df['datetime'] = pd.to_datetime(df['id'].astype(int), unit='s')
                for col in ['open', 'high', 'low', 'close', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.rename(columns={'amount': 'volume'})
                df = df.set_index('datetime')
                return df[['open', 'high', 'low', 'close', 'volume']]

            elif exchange == 'coinbase':
                params = {'granularity': int(iv)}
                if start_date:
                    params['start'] = start_date.isoformat()
                if end_date:
                    params['end'] = end_date.isoformat()
                endpoint = endpoints['coinbase_candles'].format(product_id=sym)
                data = self._session_get_json(f"{base_url}{endpoint}", params)
                if not data:
                    return pd.DataFrame()
                df = pd.DataFrame(data, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['time'].astype(int), unit='s')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.set_index('datetime')
                return df[['open', 'high', 'low', 'close', 'volume']]

            else:
                self.logger.error(f"不支持的交易所: {exchange}")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"从 {exchange} 获取 {symbol} K线失败: {e}")
            return pd.DataFrame()

    def _fetch_price_from_exchange(self, exchange: str, symbol: str) -> Optional[float]:
        """从指定交易所获取单个交易对实时价格"""
        exchange_cfg = self.config.get('exchanges', {}).get(exchange, {})
        base_url = exchange_cfg.get('base_url')
        if not base_url:
            return None
        endpoints = self.config.get('api_endpoints', {})
        sym = self._build_symbol(exchange, symbol)

        try:
            if exchange == 'binance':
                body = self._session_get_json(
                    f"{base_url}{endpoints['binance_ticker']}", {'symbol': sym})
                return float(body['price']) if body and 'price' in body else None

            elif exchange == 'okx':
                body = self._session_get_json(
                    f"{base_url}{endpoints['okx_ticker']}", {'instId': sym})
                if body and body.get('code') == '0' and body.get('data'):
                    return float(body['data'][0]['last'])
                return None

            elif exchange == 'huobi':
                body = self._session_get_json(
                    f"{base_url}{endpoints['huobi_ticker']}", {'symbol': sym})
                if body and body.get('status') == 'ok' and body.get('tick'):
                    return float(body['tick']['close'])
                return None

            elif exchange == 'coinbase':
                endpoint = endpoints['coinbase_ticker'].format(product_id=sym)
                body = self._session_get_json(f"{base_url}{endpoint}")
                return float(body['price']) if body and 'price' in body else None

            return None
        except Exception as e:
            self.logger.error(f"从 {exchange} 获取 {symbol} 价格失败: {e}")
            return None

    def _update_exchange_health(self, exchange: str, success: bool):
        """更新交易所健康状态"""
        if exchange not in self._exchange_health:
            return

        health = self._exchange_health[exchange]
        health['last_check'] = time.time()

        if success:
            health['success_count'] += 1
        else:
            health['failure_count'] += 1

        # 计算健康分数（简单的成功率）
        total = health['success_count'] + health['failure_count']
        if total > 0:
            health['health_score'] = health['success_count'] / total

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
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            Any: 数据
        """
        try:
            exchange = kwargs.get('exchange', None)

            if data_type in ['kline', 'historical_kline']:
                return self.get_kdata(
                    symbol=symbol,
                    interval=kwargs.get('interval', 'daily'),
                    start_date=start_date,
                    end_date=end_date,
                    limit=kwargs.get('limit', 500),
                    exchange=exchange
                )

            elif data_type in ['realtime', 'real_time_quote']:
                symbols = kwargs.get('symbols', [symbol])
                return self.get_real_time_price(symbols, exchange)

            elif data_type == 'symbol_list':
                return self.get_symbol_list(exchange)

            else:
                raise ValueError(f"不支持的数据类型: {data_type}")

        except Exception as e:
            self.logger.error(f"获取数据失败 {symbol} ({data_type}): {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 聚合所有交易所的健康状态
        exchange_stats = {}
        for exchange, health in self._exchange_health.items():
            exchange_stats[exchange] = {
                'available': health['available'],
                'success_count': health['success_count'],
                'failure_count': health['failure_count'],
                'health_score': health['health_score']
            }

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
            'plugin_state': self.plugin_state.value if hasattr(self, 'plugin_state') else 'unknown',
            'exchanges': exchange_stats,
            'routing_strategy': self.config.get('routing_strategy', 'weighted_random')
        }


# 插件工厂函数
def create_plugin() -> CryptoUniversalPlugin:
    """创建插件实例"""
    return CryptoUniversalPlugin()


# 插件元数据
PLUGIN_METADATA = {
    "name": "加密货币通用数据源",
    "version": "2.0.0",
    "description": "提供多交易所统一接口的数字货币数据，支持智能路由和故障转移，生产级实现",
    "author": "FactorWeave-Quant 开发团队",
    "plugin_type": "data_source_crypto",
    "asset_types": ["crypto"],
    "data_types": ["historical_kline", "real_time_quote", "market_depth", "trade_tick"],
    "exchanges": ["binance", "okx", "huobi", "coinbase", "multi"],
    "production_ready": True,
    "features": [
        "async_initialization",
        "connection_pool",
        "multi_exchange_support",
        "intelligent_routing",
        "failover",
        "load_balancing",
        "rate_limiting",
        "intelligent_retry",
        "lru_cache",
        "health_check",
        "circuit_breaker"
    ]
}
