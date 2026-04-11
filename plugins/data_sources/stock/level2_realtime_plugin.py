"""
Level-2实时数据源插件

提供Level-2实时行情数据接入，支持新浪、东方财富、腾讯等多个数据源。
基于FactorWeave-Quant标准插件模板实现，集成WebSocket实时数据推送。

作者: FactorWeave-Quant增强团队
版本: 1.0.0
日期: 2025-09-21
"""

import asyncio
import json
import time
import websocket
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from loguru import logger

from plugins.templates.standard_data_source_plugin import (
    StandardDataSourcePlugin, PluginConfig,
    PluginConnectionError, PluginDataQualityError
)
from core.plugin_types import AssetType, DataType
from core.data_source_extensions import PluginInfo, HealthCheckResult


@dataclass
class Level2Config(PluginConfig):
    """Level-2插件配置"""

    def __init__(self):
        super().__init__()

        # 数据源配置
        self.data_sources = {
            'sina': {
                'ws_url': 'wss://hq.sinajs.cn/wskt',
                'enabled': True,
                'priority': 1,
                'timeout': 30,
                'reconnect_interval': 5
            },
            'eastmoney': {
                'ws_url': 'wss://push2.eastmoney.com/api/qt/clist/get',
                'enabled': True,
                'priority': 2,
                'timeout': 30,
                'reconnect_interval': 5
            },
            'tencent': {
                'ws_url': 'wss://ws.gtimg.cn/x/kline',
                'enabled': True,
                'priority': 3,
                'timeout': 30,
                'reconnect_interval': 5
            }
        }

        # 数据类型支持
        self.supported_data_types = [
            DataType.REAL_TIME_QUOTE,
            DataType.TICK_DATA,
            DataType.ORDER_BOOK,
            DataType.LEVEL2_DATA
        ]

        # 资产类型支持
        self.supported_asset_types = [
            AssetType.STOCK_A,
            AssetType.INDEX,
            AssetType.FUND  # ETF属于基金类型
        ]

        # 性能配置
        self.max_symbols_per_connection = 100
        self.data_buffer_size = 10000
        self.heartbeat_interval = 30


class Level2RealtimePlugin(StandardDataSourcePlugin):
    """Level-2实时数据源插件"""

    def __init__(self):
        super().__init__(
            plugin_id="level2_realtime_plugin",
            plugin_name="Level-2实时数据源"
        )
        self.config = Level2Config()

        # 存储插件信息
        self._plugin_info = PluginInfo(
            id="level2_realtime_plugin",
            name="Level-2实时数据源",
            version="1.0.0",
            author="FactorWeave-Quant增强团队",
            description="提供Level-2实时行情数据，支持tick数据和订单簿数据",
            supported_data_types=self.config.supported_data_types,
            supported_asset_types=self.config.supported_asset_types,
            capabilities={
                'data_types': ['realtime_quote', 'tick_data', 'order_book', 'level2_data'],
                'asset_types': ['stock', 'index', 'etf'],
                'features': ['realtime_streaming', 'websocket', 'level2_depth', 'tick_by_tick']
            }
        )

        # WebSocket连接管理
        self._connections: Dict[str, websocket.WebSocketApp] = {}
        self._connection_status: Dict[str, bool] = {}
        self._subscriptions: Dict[str, List[str]] = {}  # source -> symbols
        self._callbacks: Dict[str, List[Callable]] = {}  # symbol -> callbacks

        # 数据缓存
        self._quote_cache: Dict[str, Dict] = {}
        self._tick_cache: Dict[str, List[Dict]] = {}
        self._order_book_cache: Dict[str, Dict] = {}

        # 线程管理
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._running = False
        self._lock = threading.RLock()

        logger.info("Level-2实时数据源插件初始化完成")

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return self._plugin_info

    # 实现StandardDataSourcePlugin的抽象方法
    def get_version(self) -> str:
        """获取插件版本"""
        return "1.0.0"

    def get_description(self) -> str:
        """获取插件描述"""
        return "提供Level-2实时行情数据，支持tick数据和订单簿数据"

    def get_author(self) -> str:
        """获取插件作者"""
        return "FactorWeave-Quant增强团队"

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return self.config.supported_asset_types

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return self.config.supported_data_types

    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力（兼容 EnhancedRealtimeDataManager 的能力匹配格式）"""
        base_capabilities = self.plugin_info.capabilities.copy() if self.plugin_info.capabilities else {}
        base_capabilities.update({
            'tick': True,
            'level2': True,
            'order_book': True,
            'realtime': True,
        })
        return base_capabilities

    def _internal_connect(self, **kwargs) -> bool:
        """内部连接实现"""
        return self.connect()

    def _internal_disconnect(self) -> bool:
        """内部断开连接实现"""
        return self.disconnect()

    def _internal_get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """内部获取资产列表实现"""
        return self.get_asset_list(asset_type, market)

    def _internal_get_kdata(self, symbol: str, freq: str = "D",
                            start_date: str = None, end_date: str = None,
                            count: int = None) -> pd.DataFrame:
        """内部获取K线数据实现"""
        return self.get_kdata(symbol, freq, start_date, end_date, count)

    def _internal_get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """内部获取实时行情实现"""
        quotes = []
        for symbol in symbols:
            quote = self.get_realtime_quote(symbol)
            if quote:
                quotes.append(quote)
        return quotes

    def initialize(self) -> bool:
        """初始化插件"""
        try:
            logger.info("初始化Level-2实时数据源插件")

            # 初始化数据源连接状态
            for source_id in self.config.data_sources:
                self._connection_status[source_id] = False
                self._subscriptions[source_id] = []

            self._running = True
            logger.info("Level-2实时数据源插件初始化成功")
            return True

        except Exception as e:
            logger.error(f"Level-2实时数据源插件初始化失败: {e}")
            return False

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            # 检查连接状态
            total_sources = len(self.config.data_sources)
            connected_sources = sum(1 for status in self._connection_status.values() if status)

            health_score = connected_sources / total_sources if total_sources > 0 else 0

            details = {
                'total_sources': total_sources,
                'connected_sources': connected_sources,
                'connection_status': self._connection_status.copy(),
                'active_subscriptions': sum(len(symbols) for symbols in self._subscriptions.values())
            }

            is_healthy = health_score >= 0.5  # 至少50%的数据源可用

            return HealthCheckResult(
                is_healthy=is_healthy,
                score=health_score,
                message=f"连接状态: {connected_sources}/{total_sources}",
                details=details,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Level-2插件健康检查失败: {e}")
            return HealthCheckResult(
                is_healthy=False,
                score=0.0,
                message=f"健康检查失败: {e}",
                details={},
                timestamp=datetime.now()
            )

    def connect(self) -> bool:
        """连接数据源"""
        try:
            logger.info("连接Level-2数据源")

            success_count = 0
            for source_id, config in self.config.data_sources.items():
                if config['enabled']:
                    if self._connect_websocket(source_id, config):
                        success_count += 1

            # 至少有一个数据源连接成功即可
            connected = success_count > 0
            if connected:
                logger.info(f"Level-2数据源连接成功: {success_count} 个数据源")
            else:
                logger.error("所有Level-2数据源连接失败")

            return connected

        except Exception as e:
            logger.error(f"连接Level-2数据源失败: {e}")
            return False

    def disconnect(self) -> bool:
        """断开数据源连接"""
        try:
            logger.info("断开Level-2数据源连接")

            # 关闭所有WebSocket连接
            for source_id, ws in self._connections.items():
                try:
                    ws.close()
                    self._connection_status[source_id] = False
                except Exception as e:
                    logger.error(f"关闭WebSocket连接失败 {source_id}: {e}")

            self._connections.clear()
            self._running = False

            # 关闭线程池
            self._executor.shutdown(wait=True)

            logger.info("Level-2数据源连接已断开")
            return True

        except Exception as e:
            logger.error(f"断开Level-2数据源连接失败: {e}")
            return False

    def _connect_websocket(self, source_id: str, config: Dict) -> bool:
        """连接WebSocket"""
        try:
            def on_message(ws, message):
                self._handle_websocket_message(source_id, message)

            def on_error(ws, error):
                logger.error(f"WebSocket错误 {source_id}: {error}")
                self._connection_status[source_id] = False

            def on_close(ws, close_status_code, close_msg):
                logger.warning(f"WebSocket连接关闭 {source_id}: {close_status_code}")
                self._connection_status[source_id] = False

                # 自动重连
                if self._running:
                    self._schedule_reconnect(source_id, config)

            def on_open(ws):
                logger.info(f"WebSocket连接已建立: {source_id}")
                self._connection_status[source_id] = True

                # 发送心跳
                self._start_heartbeat(source_id, ws)

            ws_app = websocket.WebSocketApp(
                config['ws_url'],
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )

            self._connections[source_id] = ws_app

            # 在后台线程中运行WebSocket
            self._executor.submit(ws_app.run_forever)

            # 等待连接建立
            time.sleep(2)

            return self._connection_status.get(source_id, False)

        except Exception as e:
            logger.error(f"连接WebSocket失败 {source_id}: {e}")
            return False

    def _handle_websocket_message(self, source_id: str, message: str):
        """处理WebSocket消息"""
        try:
            # 解析JSON消息
            data = json.loads(message) if isinstance(message, str) else message

            # 根据数据源类型处理消息
            if source_id == 'sina':
                self._handle_sina_message(data)
            elif source_id == 'eastmoney':
                self._handle_eastmoney_message(data)
            elif source_id == 'tencent':
                self._handle_tencent_message(data)

        except Exception as e:
            logger.error(f"处理WebSocket消息失败 {source_id}: {e}")

    def _handle_sina_message(self, data: Dict):
        """处理新浪数据"""
        try:
            if 'symbol' in data and 'price' in data:
                symbol = data['symbol']

                # 更新实时行情缓存
                self._quote_cache[symbol] = {
                    'symbol': symbol,
                    'timestamp': datetime.now(),
                    'last_price': float(data.get('price', 0)),
                    'bid_price': float(data.get('bid1', 0)),
                    'ask_price': float(data.get('ask1', 0)),
                    'volume': int(data.get('volume', 0)),
                    'turnover': float(data.get('amount', 0))
                }

                # 如果有tick数据，添加到tick缓存
                if 'trade_time' in data:
                    tick_data = {
                        'symbol': symbol,
                        'timestamp': datetime.now(),
                        'price': float(data.get('price', 0)),
                        'volume': int(data.get('trade_volume', 0)),
                        'direction': data.get('direction', 'N')
                    }

                    if symbol not in self._tick_cache:
                        self._tick_cache[symbol] = []

                    self._tick_cache[symbol].append(tick_data)

                    # 限制缓存大小
                    if len(self._tick_cache[symbol]) > self.config.data_buffer_size:
                        self._tick_cache[symbol] = self._tick_cache[symbol][-self.config.data_buffer_size:]

                # 通知回调函数
                self._notify_callbacks(symbol, 'quote', self._quote_cache[symbol])

        except Exception as e:
            logger.error(f"处理新浪数据失败: {e}")

    def _handle_eastmoney_message(self, data: Dict):
        """处理东方财富数据"""
        try:
            # 东方财富数据格式处理
            if 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    symbol = item.get('f12', '')  # 股票代码
                    if symbol:
                        self._quote_cache[symbol] = {
                            'symbol': symbol,
                            'timestamp': datetime.now(),
                            'last_price': float(item.get('f2', 0)),  # 最新价
                            'bid_price': float(item.get('f31', 0)),  # 买一价
                            'ask_price': float(item.get('f32', 0)),  # 卖一价
                            'volume': int(item.get('f5', 0)),        # 成交量
                            'turnover': float(item.get('f6', 0))     # 成交额
                        }

                        self._notify_callbacks(symbol, 'quote', self._quote_cache[symbol])

        except Exception as e:
            logger.error(f"处理东方财富数据失败: {e}")

    def _handle_tencent_message(self, data: Dict):
        """处理腾讯数据"""
        try:
            # 腾讯数据格式处理
            if 'data' in data:
                for symbol, quote_data in data['data'].items():
                    self._quote_cache[symbol] = {
                        'symbol': symbol,
                        'timestamp': datetime.now(),
                        'last_price': float(quote_data.get('3', 0)),   # 最新价
                        'bid_price': float(quote_data.get('10', 0)),   # 买一价
                        'ask_price': float(quote_data.get('20', 0)),   # 卖一价
                        'volume': int(quote_data.get('6', 0)),         # 成交量
                        'turnover': float(quote_data.get('37', 0))     # 成交额
                    }

                    self._notify_callbacks(symbol, 'quote', self._quote_cache[symbol])

        except Exception as e:
            logger.error(f"处理腾讯数据失败: {e}")

    def _notify_callbacks(self, symbol: str, data_type: str, data: Dict):
        """通知回调函数"""
        try:
            callbacks = self._callbacks.get(symbol, [])
            for callback in callbacks:
                try:
                    callback(data_type, symbol, data)
                except Exception as e:
                    logger.error(f"回调函数执行失败: {e}")
        except Exception as e:
            logger.error(f"通知回调函数失败: {e}")

    def _start_heartbeat(self, source_id: str, ws: websocket.WebSocketApp):
        """启动心跳"""
        def heartbeat():
            while self._running and self._connection_status.get(source_id, False):
                try:
                    # 发送心跳消息
                    heartbeat_msg = json.dumps({'type': 'ping', 'timestamp': time.time()})
                    ws.send(heartbeat_msg)
                    time.sleep(self.config.heartbeat_interval)
                except Exception as e:
                    logger.error(f"发送心跳失败 {source_id}: {e}")
                    break

        self._executor.submit(heartbeat)

    def _schedule_reconnect(self, source_id: str, config: Dict):
        """安排重连"""
        def reconnect():
            time.sleep(config['reconnect_interval'])
            if self._running:
                logger.info(f"尝试重连WebSocket: {source_id}")
                self._connect_websocket(source_id, config)

        self._executor.submit(reconnect)

    def subscribe_realtime_data(self, symbols: List[str], callback: Callable) -> bool:
        """订阅实时数据"""
        try:
            logger.info(f"订阅实时数据: {symbols}")

            for symbol in symbols:
                if symbol not in self._callbacks:
                    self._callbacks[symbol] = []

                self._callbacks[symbol].append(callback)

                # 向所有可用数据源发送订阅请求
                for source_id, ws in self._connections.items():
                    if self._connection_status.get(source_id, False):
                        subscribe_msg = self._build_subscribe_message(source_id, symbol)
                        if subscribe_msg:
                            ws.send(subscribe_msg)

                            if source_id not in self._subscriptions:
                                self._subscriptions[source_id] = []
                            self._subscriptions[source_id].append(symbol)

            return True

        except Exception as e:
            logger.error(f"订阅实时数据失败: {e}")
            return False

    def _build_subscribe_message(self, source_id: str, symbol: str) -> Optional[str]:
        """构建订阅消息"""
        try:
            if source_id == 'sina':
                return json.dumps({
                    'cmd': 'subscribe',
                    'symbol': symbol,
                    'type': 'level2'
                })
            elif source_id == 'eastmoney':
                return json.dumps({
                    'action': 'subscribe',
                    'code': symbol,
                    'level': 2
                })
            elif source_id == 'tencent':
                return json.dumps({
                    'req': 'subscribe',
                    'symbol': symbol,
                    'depth': 10
                })

            return None

        except Exception as e:
            logger.error(f"构建订阅消息失败: {e}")
            return None

    def get_realtime_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        try:
            return self._quote_cache.get(symbol)
        except Exception as e:
            logger.error(f"获取实时行情失败: {symbol}, {e}")
            return None

    def get_tick_data(self, symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """获取tick数据"""
        try:
            tick_list = self._tick_cache.get(symbol, [])

            # 过滤时间范围
            filtered_ticks = [
                tick for tick in tick_list
                if start_time <= tick['timestamp'] <= end_time
            ]

            if not filtered_ticks:
                return pd.DataFrame()

            return pd.DataFrame(filtered_ticks)

        except Exception as e:
            logger.error(f"获取tick数据失败: {symbol}, {e}")
            return pd.DataFrame()

    def get_order_book(self, symbol: str) -> Optional[Dict]:
        """获取订单簿数据"""
        try:
            return self._order_book_cache.get(symbol)
        except Exception as e:
            logger.error(f"获取订单簿数据失败: {symbol}, {e}")
            return None

    def get_supported_symbols(self) -> List[str]:
        """获取支持的股票代码列表"""
        # 返回当前缓存中的所有股票代码
        return list(self._quote_cache.keys())

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            # Level-2插件主要提供实时数据，返回当前订阅的资产
            assets = []
            for symbol in self._quote_cache.keys():
                assets.append({
                    'code': symbol,
                    'name': f"Level-2实时数据-{symbol}",
                    'type': 'stock',
                    'market': 'realtime',
                    'source': 'level2_realtime'
                })
            return assets
        except Exception as e:
            logger.error(f"获取资产列表失败: {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """获取K线数据"""
        try:
            # Level-2插件主要提供实时数据，K线数据需要从其他数据源获取
            logger.warning(f"Level-2插件不提供K线数据，请使用其他数据源获取 {symbol} 的K线数据")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()

    def cleanup(self):
        """清理资源"""
        try:
            self.disconnect()
            self._quote_cache.clear()
            self._tick_cache.clear()
            self._order_book_cache.clear()
            self._callbacks.clear()
            logger.info("Level-2插件资源清理完成")
        except Exception as e:
            logger.error(f"Level-2插件资源清理失败: {e}")

# 插件工厂函数


def create_plugin() -> Level2RealtimePlugin:
    """创建插件实例"""
    return Level2RealtimePlugin()


# 插件元数据
PLUGIN_METADATA = {
    'name': 'Level-2实时数据源',
    'version': '1.0.0',
    'author': 'FactorWeave-Quant增强团队',
    'description': '提供Level-2实时行情数据，支持tick数据和订单簿数据',
    'plugin_class': Level2RealtimePlugin,
    'factory_function': create_plugin,
    'supported_data_types': [
        DataType.REAL_TIME_QUOTE,
        DataType.TICK_DATA,
        DataType.ORDER_BOOK,
        DataType.LEVEL2_DATA
    ],
    'supported_asset_types': [
        AssetType.STOCK_A,
        AssetType.INDEX,
        AssetType.FUND  # ETF属于基金类型
    ],
    'capabilities': {
        'data_types': ['realtime_quote', 'tick_data', 'order_book', 'level2_data'],
        'asset_types': ['stock', 'index', 'etf'],
        'features': ['realtime_streaming', 'websocket', 'level2_depth', 'tick_by_tick']
    }
}
