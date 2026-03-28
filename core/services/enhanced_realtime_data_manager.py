#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Realtime Data Manager
增强实时数据管理器

基于现有系统架构，提供专业级Level-2实时行情数据管理功能。
使用真实的数据源API和WebSocket连接，支持Tick数据、订单簿数据等高频数据处理。

主要功能：
1. 实时数据订阅和管理
2. WebSocket连接管理
3. 数据标准化和验证
4. 事件总线集成
5. 数据缓冲和流控制

作者: FactorWeave-Quant Team
版本: 1.0.0
日期: 2024
"""

import asyncio
import websocket
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from loguru import logger
import pandas as pd
from collections import defaultdict, deque
import threading

from core.plugin_types import AssetType, DataType
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.tet_data_pipeline import StandardQuery, StandardData
from core.data_standardization_engine import DataStandardizationEngine
from core.data_validator import DataValidator
from core.events.event_bus import EventBus, RealtimeDataEvent, OrderBookEvent, TickDataEvent

logger = logger.bind(module=__name__)


class EnhancedRealtimeDataManager:
    """
    增强实时行情数据管理器
    负责Level-2、Tick数据和订单簿数据的获取、处理、标准化和分发。
    使用真实的数据源API，不包含任何模拟数据。
    """

    def __init__(self, event_bus: EventBus, data_standardizer: DataStandardizationEngine, data_validator: DataValidator, uni_plugin_manager: 'UniPluginDataManager'):
        self.event_bus = event_bus
        self.data_standardizer = data_standardizer
        self.data_validator = data_validator
        self.uni_plugin_manager = uni_plugin_manager  # 通过TET框架调用插件
        self.websocket_connections: Dict[str, Any] = {}  # 管理WebSocket连接
        self.data_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))  # 实时数据缓冲区
        self.subscription_status: Dict[str, Dict[str, bool]] = {}  # 订阅状态
        self.connection_lock = threading.RLock()
        self.realtime_plugins: Dict[str, IDataSourcePlugin] = {}  # 实时数据源插件注册表
        logger.info("EnhancedRealtimeDataManager 初始化完成，集成TET框架。")

    async def register_realtime_plugin(self, plugin_id: str, plugin: IDataSourcePlugin):
        """
        注册实时数据源插件
        注意：实际上应该通过原有的PluginCenter自动发现和注册，这个方法主要用于兼容性
        """
        logger.info(f"实时数据源插件 '{plugin_id}' 注册请求，建议通过PluginCenter自动发现")

        # 检查插件是否已在TET框架中注册
        if self.uni_plugin_manager and hasattr(self.uni_plugin_manager, 'plugin_center'):
            plugin_center = self.uni_plugin_manager.plugin_center
            if plugin_id in plugin_center.data_source_plugins:
                logger.info(f"插件 '{plugin_id}' 已在TET框架中注册")
            else:
                # 通过PluginCenter注册
                success = plugin_center._register_data_source_plugin(plugin_id, plugin)
                if success:
                    logger.info(f"插件 '{plugin_id}' 已通过PluginCenter注册到TET框架")
                else:
                    logger.warning(f"插件 '{plugin_id}' 注册到TET框架失败")
        else:
            logger.warning(f"UniPluginManager 为空，跳过TET框架注册")

        # 同时注册到本地插件表
        self.realtime_plugins[plugin_id] = plugin
        logger.info(f"插件 '{plugin_id}' 已注册到实时数据管理器")

    async def subscribe_realtime_data(self, symbols: List[str], data_types: List[DataType], asset_type: AssetType, source_plugin_id: Optional[str] = None):
        """
        订阅实时数据（Level-2, Tick等）
        直接通过插件接口订阅，不依赖不存在的 TET 框架方法
        """
        logger.info(f"订阅实时数据: 股票={symbols}, 类型={data_types}, 资产={asset_type}, 插件={source_plugin_id}")

        for data_type in data_types:
            for symbol in symbols:
                try:
                    # 直接通过插件订阅（不依赖 TET 框架）
                    if source_plugin_id and source_plugin_id in self.realtime_plugins:
                        plugin = self.realtime_plugins[source_plugin_id]
                        asyncio.create_task(self._maintain_realtime_subscription(symbol, data_type, asset_type, source_plugin_id))
                        logger.info(f"通过指定插件 {source_plugin_id} 成功订阅 {symbol} 的 {data_type.value} 数据")
                    elif self.realtime_plugins:
                        # 使用默认插件
                        default_plugin_id = self._select_default_plugin(data_type)
                        if default_plugin_id:
                            asyncio.create_task(self._maintain_realtime_subscription(symbol, data_type, asset_type, default_plugin_id))
                            logger.info(f"通过默认插件 {default_plugin_id} 成功订阅 {symbol} 的 {data_type.value} 数据")
                        else:
                            logger.error(f"没有可用的插件来订阅 {symbol} 的 {data_type.value} 数据")
                    else:
                        logger.error(f"没有可用的插件来订阅 {symbol} 的 {data_type.value} 数据")

                except Exception as e:
                    logger.error(f"订阅实时数据失败: {symbol} - {data_type.value}: {e}")

    async def _maintain_realtime_subscription(
        self,
        symbol: str,
        data_type: DataType,
        asset_type: AssetType,
        source_plugin_id: Optional[str] = None
    ):
        """维护实时数据订阅（轮询任务）"""
        try:
            plugin_id = source_plugin_id
            plugin = None

            if not plugin_id:
                plugin_id = self._select_default_plugin(data_type)

            plugin = self.realtime_plugins.get(plugin_id)
            if not plugin:
                logger.error(f"插件 {plugin_id} 未注册到实时数据管理器")
                return

            logger.info(f"开始维护 {symbol} 的 {data_type.value} 数据订阅，插件: {plugin_id}")

            if data_type == DataType.TICK_DATA:
                await self._poll_tick_data(plugin_id, plugin, [symbol], asset_type)
            elif data_type == DataType.LEVEL2_DATA:
                await self._poll_realtime_data(plugin_id, plugin, [symbol], data_type, asset_type)
            elif data_type == DataType.ORDER_BOOK:
                await self._poll_order_book_data(plugin_id, plugin, [symbol], asset_type)
            else:
                logger.warning(f"不支持的数据类型: {data_type}")

        except Exception as e:
            logger.error(f"维护实时订阅失败: {e}")

    def _select_default_plugin(self, data_type: DataType) -> str:
        """选择默认插件（根据数据类型能力匹配）"""
        if not self.realtime_plugins:
            return ""

        capability_map = {
            DataType.TICK_DATA: 'tick',
            DataType.LEVEL2_DATA: 'level2',
            DataType.ORDER_BOOK: 'order_book',
        }
        required_capability = capability_map.get(data_type)

        for plugin_id, plugin in self.realtime_plugins.items():
            if required_capability:
                if hasattr(plugin, 'get_capabilities'):
                    capabilities = plugin.get_capabilities()
                    if capabilities.get(required_capability, False):
                        return plugin_id
                continue
            return plugin_id

        return ""

    def _ensure_subscription_status(self, plugin_id: str) -> None:
        """确保订阅状态已初始化"""
        if plugin_id not in self.subscription_status:
            self.subscription_status[plugin_id] = {}

    async def _subscribe_via_plugin(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], data_types: List[DataType], asset_type: AssetType):
        """通过特定插件订阅实时数据"""

        # 根据数据类型调用不同的订阅方法
        for data_type in data_types:
            try:
                if data_type == DataType.LEVEL2_DATA:
                    await self._subscribe_level2_data(plugin_id, plugin, symbols, asset_type)
                elif data_type == DataType.TICK_DATA:
                    await self._subscribe_tick_data(plugin_id, plugin, symbols, asset_type)
                elif data_type == DataType.ORDER_BOOK:
                    await self._subscribe_order_book_data(plugin_id, plugin, symbols, asset_type)
                else:
                    logger.warning(f"不支持的数据类型: {data_type}")

            except Exception as e:
                logger.error(f"订阅 {data_type} 数据失败，插件 {plugin_id}: {e}")

    async def _subscribe_level2_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], asset_type: AssetType):
        """订阅Level-2数据"""
        try:
            # 检查插件是否有Level-2数据订阅方法
            if hasattr(plugin, 'subscribe_level2_data'):
                await plugin.subscribe_level2_data(symbols, asset_type)
                logger.info(f"插件 {plugin_id} Level-2数据订阅成功")
            elif hasattr(plugin, 'get_real_time_data'):
                # 使用实时数据获取方法
                asyncio.create_task(self._poll_realtime_data(plugin_id, plugin, symbols, DataType.LEVEL2_DATA, asset_type))
                logger.info(f"插件 {plugin_id} 开始轮询Level-2数据")
            else:
                logger.warning(f"插件 {plugin_id} 不支持Level-2数据订阅")

        except Exception as e:
            logger.error(f"订阅Level-2数据失败，插件 {plugin_id}: {e}")

    async def _subscribe_tick_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], asset_type: AssetType):
        """订阅Tick数据"""
        try:
            if hasattr(plugin, 'subscribe_tick_data'):
                await plugin.subscribe_tick_data(symbols, asset_type)
                logger.info(f"插件 {plugin_id} Tick数据订阅成功")
            elif hasattr(plugin, 'get_tick_data'):
                # 使用Tick数据获取方法
                asyncio.create_task(self._poll_tick_data(plugin_id, plugin, symbols, asset_type))
                logger.info(f"插件 {plugin_id} 开始轮询Tick数据")
            else:
                logger.warning(f"插件 {plugin_id} 不支持Tick数据订阅")

        except Exception as e:
            logger.error(f"订阅Tick数据失败，插件 {plugin_id}: {e}")

    async def _subscribe_order_book_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], asset_type: AssetType):
        """订阅订单簿数据"""
        try:
            if hasattr(plugin, 'subscribe_order_book'):
                await plugin.subscribe_order_book(symbols, asset_type)
                logger.info(f"插件 {plugin_id} 订单簿数据订阅成功")
            elif hasattr(plugin, 'get_order_book'):
                # 使用订单簿数据获取方法
                asyncio.create_task(self._poll_order_book_data(plugin_id, plugin, symbols, asset_type))
                logger.info(f"插件 {plugin_id} 开始轮询订单簿数据")
            else:
                logger.warning(f"插件 {plugin_id} 不支持订单簿数据订阅")

        except Exception as e:
            logger.error(f"订阅订单簿数据失败，插件 {plugin_id}: {e}")

    async def _poll_realtime_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], data_type: DataType, asset_type: AssetType):
        """轮询实时数据"""
        self._ensure_subscription_status(plugin_id)
        subscription_key = f"{plugin_id}_{data_type.value}"
        self.subscription_status[plugin_id][subscription_key] = True

        while self.subscription_status[plugin_id].get(subscription_key, False):
            try:
                # 获取实时数据
                if hasattr(plugin, 'get_real_time_data'):
                    raw_data = plugin.get_real_time_data(symbols)
                    if raw_data is not None and not raw_data.empty:
                        await self._process_realtime_data(plugin_id, raw_data, data_type)

                # 控制轮询频率
                await asyncio.sleep(1)  # 1秒轮询一次

            except Exception as e:
                logger.error(f"轮询实时数据失败，插件 {plugin_id}: {e}")
                await asyncio.sleep(5)  # 错误时延长等待时间

    async def _poll_tick_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], asset_type: AssetType):
        """轮询Tick数据"""
        self._ensure_subscription_status(plugin_id)
        subscription_key = f"{plugin_id}_tick"
        self.subscription_status[plugin_id][subscription_key] = True

        while self.subscription_status[plugin_id].get(subscription_key, False):
            try:
                for symbol in symbols:
                    if hasattr(plugin, 'get_tick_data'):
                        # 获取最近的Tick数据
                        end_time = datetime.now()
                        start_time = end_time - timedelta(seconds=60)  # 获取最近1分钟的数据

                        tick_data = plugin.get_tick_data(symbol, start_time, end_time, asset_type)
                        if tick_data:
                            await self._process_tick_data(plugin_id, symbol, tick_data)

                await asyncio.sleep(0.5)  # Tick数据更频繁

            except Exception as e:
                logger.error(f"轮询Tick数据失败，插件 {plugin_id}: {e}")
                await asyncio.sleep(2)

    async def _poll_order_book_data(self, plugin_id: str, plugin: IDataSourcePlugin, symbols: List[str], asset_type: AssetType):
        """轮询订单簿数据"""
        self._ensure_subscription_status(plugin_id)
        subscription_key = f"{plugin_id}_orderbook"
        self.subscription_status[plugin_id][subscription_key] = True

        while self.subscription_status[plugin_id].get(subscription_key, False):
            try:
                for symbol in symbols:
                    if hasattr(plugin, 'get_order_book'):
                        order_book = plugin.get_order_book(symbol, datetime.now(), asset_type)
                        if order_book:
                            await self._process_order_book_data(plugin_id, symbol, order_book)

                await asyncio.sleep(1)  # 订单簿数据1秒更新

            except Exception as e:
                logger.error(f"轮询订单簿数据失败，插件 {plugin_id}: {e}")
                await asyncio.sleep(3)

    async def _process_realtime_data(self, plugin_id: str, raw_data: pd.DataFrame, data_type: DataType):
        """处理实时数据"""
        try:
            # 数据标准化
            for _, row in raw_data.iterrows():
                standard_data = row.to_dict()

                if self.data_standardizer:
                    standard_data = self.data_standardizer.standardize_realtime_data(standard_data, data_type, plugin_id)

                if not standard_data:
                    continue

                should_validate = self.data_validator is not None
                is_valid = True
                if should_validate:
                    is_valid = self.data_validator.validate_realtime_data(standard_data, data_type)

                if is_valid:
                    # 添加到缓冲区
                    symbol = standard_data.get('symbol')
                    if symbol:
                        self.data_buffers[symbol].append(standard_data)

                    # 发布事件
                    event = RealtimeDataEvent(realtime_data=standard_data)
                    await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"处理实时数据失败，插件 {plugin_id}: {e}")

    async def _process_tick_data(self, plugin_id: str, symbol: str, tick_data):
        """处理Tick数据"""
        try:
            # 如果是 DataFrame，转换为 List[Dict]
            if hasattr(tick_data, 'to_dict'):
                tick_list = tick_data.to_dict('records')
            else:
                tick_list = tick_data

            for tick in tick_list:
                standard_tick = tick

                if self.data_standardizer:
                    standard_tick = self.data_standardizer.standardize_realtime_data(standard_tick, DataType.TICK_DATA, plugin_id)

                if not standard_tick:
                    continue

                should_validate = self.data_validator is not None
                is_valid = True
                if should_validate:
                    is_valid = self.data_validator.validate_realtime_data(standard_tick, DataType.TICK_DATA)

                if is_valid:
                    # 添加到缓冲区
                    self.data_buffers[symbol].append(standard_tick)

                    # 发布事件
                    event = TickDataEvent(tick_data=standard_tick)
                    await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"处理Tick数据失败，插件 {plugin_id}: {e}")

    async def _process_order_book_data(self, plugin_id: str, symbol: str, order_book: Dict):
        """处理订单簿数据"""
        try:
            standard_order_book = order_book

            if self.data_standardizer:
                standard_order_book = self.data_standardizer.standardize_realtime_data(standard_order_book, DataType.ORDER_BOOK, plugin_id)

            if not standard_order_book:
                return

            should_validate = self.data_validator is not None
            is_valid = True
            if should_validate:
                is_valid = self.data_validator.validate_realtime_data(standard_order_book, DataType.ORDER_BOOK)

            if is_valid:
                # 添加到缓冲区
                self.data_buffers[symbol].append(standard_order_book)

                # 发布事件
                event = OrderBookEvent(order_book_data=standard_order_book)
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"处理订单簿数据失败，插件 {plugin_id}: {e}")

    def get_tick_data(self, symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        获取指定时间范围内的tick级别历史数据
        从DuckDB或其他历史数据库中查询
        """
        logger.info(f"从历史数据源获取tick数据: {symbol} 从 {start_time} 到 {end_time}")

        try:
            # 这里应该连接到真实的数据库查询
            # 例如：从DuckDB查询历史Tick数据
            from core.database.duckdb_manager import DuckDBManager

            duckdb_manager = DuckDBManager()
            query = """
                SELECT symbol, timestamp, price, volume, trade_type, source
                FROM tick_data 
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """

            result_df = duckdb_manager.query(query, params=[symbol, start_time.isoformat(), end_time.isoformat()])

            if result_df is not None and not result_df.empty:
                logger.info(f"从DuckDB获取到 {len(result_df)} 条tick数据")
                return result_df
            else:
                logger.warning(f"未找到 {symbol} 在指定时间范围的tick数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取tick历史数据失败: {e}")
            return pd.DataFrame()

    def get_order_book(self, symbol: str, timestamp: datetime, depth: int = 10) -> Dict[str, Any]:
        """
        获取指定时间点的订单簿快照
        从DuckDB或其他历史数据库中查询
        """
        logger.info(f"从历史数据源获取订单簿快照: {symbol} 在 {timestamp}")

        try:
            # 从DuckDB查询订单簿历史数据
            from core.database.duckdb_manager import DuckDBManager

            duckdb_manager = DuckDBManager()
            query = """
                SELECT symbol, timestamp, bids, asks, source
                FROM order_book_snapshots 
                WHERE symbol = ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """

            result = duckdb_manager.query(query, params=[symbol, timestamp.isoformat()])

            if result is not None and not result.empty:
                row = result.iloc[0]
                return {
                    "symbol": row['symbol'],
                    "timestamp": row['timestamp'],
                    "bids": json.loads(row['bids']) if isinstance(row['bids'], str) else row['bids'],
                    "asks": json.loads(row['asks']) if isinstance(row['asks'], str) else row['asks'],
                    "source": row['source']
                }
            else:
                logger.warning(f"未找到 {symbol} 在 {timestamp} 的订单簿数据")
                return {}

        except Exception as e:
            logger.error(f"获取订单簿历史数据失败: {e}")
            return {}

    async def unsubscribe_realtime_data(self, symbols: List[str], data_types: List[DataType], source_plugin_id: Optional[str] = None):
        """取消订阅实时数据"""
        logger.info(f"取消订阅实时数据: {symbols}, 类型: {data_types}, 插件: {source_plugin_id}")

        for plugin_id in self.realtime_plugins:
            if source_plugin_id and plugin_id != source_plugin_id:
                continue

            # 停止订阅
            for data_type in data_types:
                subscription_key = f"{plugin_id}_{data_type.value}"
                if subscription_key in self.subscription_status.get(plugin_id, {}):
                    self.subscription_status[plugin_id][subscription_key] = False
                    logger.info(f"已停止插件 {plugin_id} 的 {data_type.value} 数据订阅")

    def get_subscription_status(self) -> Dict[str, Dict[str, bool]]:
        """获取订阅状态"""
        return self.subscription_status.copy()

    def get_buffered_data(self, symbol: str, limit: int = 100) -> List[Dict]:
        """获取缓冲的数据"""
        buffer = self.data_buffers.get(symbol, deque())
        return list(buffer)[-limit:] if buffer else []

    async def cleanup(self):
        """清理资源"""
        logger.info("开始清理实时数据管理器资源...")

        # 停止所有订阅
        for plugin_id in self.subscription_status:
            for subscription_key in self.subscription_status[plugin_id]:
                self.subscription_status[plugin_id][subscription_key] = False

        # 关闭WebSocket连接
        for connection in self.websocket_connections.values():
            try:
                if hasattr(connection, 'close'):
                    connection.close()
            except Exception as e:
                logger.warning(f"关闭WebSocket连接失败: {e}")

        self.websocket_connections.clear()
        logger.info("实时数据管理器资源清理完成")
