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
import queue
import time as time_module
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Callable
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
from core.database.duckdb_manager import get_connection_manager

logger = logger.bind(module=__name__)

MAIN_DATABASE_PATH = "data/factorweave_analytics.duckdb"


class PluginCallbackAdapter:
    """
    插件回调适配器
    统一不同插件的 callback 签名差异

    Level2RealtimePlugin: callback(data_type, symbol, data) - 三个参数
    MiniQMTPlugin: callback(data) - 一个参数
    """

    def __init__(self, enhanced_manager: 'EnhancedRealtimeDataManager', plugin_id: str, data_type: DataType):
        self.enhanced_manager = enhanced_manager
        self.plugin_id = plugin_id
        self.data_type = data_type
        self._is_level2_plugin = 'level2' in plugin_id.lower()

    def __call__(self, *args, **kwargs):
        """统一调用入口，适配不同插件的 callback 签名"""
        try:
            if self._is_level2_plugin:
                data_type = args[0] if len(args) > 0 else kwargs.get('data_type', '')
                symbol = args[1] if len(args) > 1 else kwargs.get('symbol', '')
                data = args[2] if len(args) > 2 else kwargs.get('data', {})
            else:
                data = args[0] if len(args) > 0 else kwargs.get('data', {})
                symbol = data.get('symbol', '') if isinstance(data, dict) else ''
                data_type = self.data_type.value

            if not symbol:
                logger.warning(f"Callback 缺少 symbol 参数，插件: {self.plugin_id}")
                return

            self.enhanced_manager._queue_callback_data(
                self.plugin_id, symbol, data_type, data
            )
        except Exception as e:
            logger.error(f"PluginCallbackAdapter 执行失败: {e}")


class EnhancedRealtimeDataManager:
    """
    增强实时行情数据管理器
    负责Level-2、Tick数据和订单簿数据的获取、处理、标准化和分发。
    使用真实的数据源API，不包含任何模拟数据。

    支持两种数据获取模式：
    1. 轮询模式（默认）：定期调用插件的 get_real_time_data 方法获取数据
    2. Callback 模式（推荐）：注册 callback 函数，插件通过 WebSocket 收到数据后立即回调
           优势：延迟更低（<100ms vs ~1秒），数据更实时
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

        # Callback 模式相关属性
        self._callback_queue: queue.Queue = queue.Queue(maxsize=1000)  # 线程安全的数据队列
        self._use_callback_mode: bool = True  # 是否启用 callback 模式
        self._callback_mode_started: bool = False  # Callback 处理协程是否已启动
        self._callback_mode_lock: threading.Lock = threading.Lock()  # 确保协程只启动一次

        # Level-2 数据缓存管理（集成 get_level2_data 用）
        self._level2_cache: Dict[str, Dict] = {}  # symbol -> data 缓存
        self._cache_timestamps: Dict[str, datetime] = {}  # symbol -> timestamp 缓存时间戳
        self._cache_ttl_seconds: int = 5  # 缓存有效期（秒）
        self._cache_lock: threading.Lock = threading.Lock()  # 缓存访问锁

        # 降级策略监控
        self._fallback_stats: Dict[str, Dict] = {}  # 统计降级次数
        self._last_poll_times: Dict[str, datetime] = {}  # 记录上次轮询时间
        self._poll_intervals: Dict[str, float] = {}  # 动态轮询间隔

        logger.info("EnhancedRealtimeDataManager 初始化完成，集成 TET 框架，启用 Level-2 缓存和智能降级策略")

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

        优先使用 Callback 模式以降低延迟
        注意：Callback 模式失败时会直接抛出异常，确保系统异常能够被及时发现和处理
        """
        logger.warning(f"[REALTIME_SUB] 订阅实时数据: 股票={symbols}, 类型={data_types}, 资产={asset_type}, 插件={source_plugin_id}")
        logger.warning(f"[REALTIME_SUB] 当前 realtime_plugins 状态: {list(self.realtime_plugins.keys()) if self.realtime_plugins else 'EMPTY'}")
        logger.warning(f"[REALTIME_SUB] uni_plugin_manager 状态: {self.uni_plugin_manager is not None}")

        errors = []
        for data_type in data_types:
            for symbol in symbols:
                try:
                    if source_plugin_id and source_plugin_id in self.realtime_plugins:
                        await self._subscribe_with_callback(symbol, data_type, asset_type, source_plugin_id)
                        logger.info(f"通过指定插件 {source_plugin_id} 成功订阅 {symbol} 的 {data_type.value} 数据")
                    elif self.realtime_plugins:
                        default_plugin_id = self._select_default_plugin(data_type)
                        if default_plugin_id:
                            await self._subscribe_with_callback(symbol, data_type, asset_type, default_plugin_id)
                            logger.info(f"通过默认插件 {default_plugin_id} 成功订阅 {symbol} 的 {data_type.value} 数据")
                        else:
                            error_msg = f"没有可用的插件来订阅 {symbol} 的 {data_type.value} 数据"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    else:
                        error_msg = f"没有可用的插件来订阅 {symbol} 的 {data_type.value} 数据"
                        logger.error(error_msg)
                        errors.append(error_msg)

                except (RuntimeError, AttributeError) as e:
                    # Callback 模式失败直接抛出异常，不吞掉
                    raise

        if errors:
            raise RuntimeError(f"订阅失败: {'; '.join(errors)}")

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

    async def _subscribe_with_callback(
        self,
        symbol: str,
        data_type: DataType,
        asset_type: AssetType,
        plugin_id: Optional[str] = None
    ):
        """
        使用 Callback 模式订阅数据（优先模式，降低延迟）

        优势：数据到达后立即处理，延迟 <100ms
        对比轮询模式：需要等待下次轮询，延迟 ~1秒

        注意：Callback 模式失败时会直接报错，不会回退到轮询模式
              以确保系统异常能够被及时发现和处理
        """
        if not plugin_id:
            plugin_id = self._select_default_plugin(data_type)

        plugin = self.realtime_plugins.get(plugin_id)
        if not plugin:
            error_msg = f"插件 {plugin_id} 未注册到实时数据管理器，无法订阅 {symbol} 的 {data_type.value} 数据"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # 检查插件是否支持 subscribe_realtime_data 方法
        if not hasattr(plugin, 'subscribe_realtime_data'):
            error_msg = f"插件 {plugin_id} 不支持 subscribe_realtime_data 方法，无法订阅 {symbol} 的 {data_type.value} 数据"
            logger.error(error_msg)
            raise AttributeError(error_msg)

        # 创建 callback 适配器
        adapter = PluginCallbackAdapter(self, plugin_id, data_type)

        # 确保 callback 处理协程已启动
        await self._ensure_callback_mode_started_async()

        # 调用插件的 subscribe_realtime_data 方法注册 callback
        success = plugin.subscribe_realtime_data([symbol], adapter, data_type)

        if not success:
            error_msg = f"Callback 模式订阅失败，插件 {plugin_id} 返回 False，无法订阅 {symbol} 的 {data_type.value} 数据"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        self._ensure_subscription_status(plugin_id)
        subscription_key = f"{plugin_id}_{data_type.value}"
        self.subscription_status[plugin_id][subscription_key] = True
        logger.info(f"Callback 模式订阅成功: {symbol}, 插件: {plugin_id}, 类型: {data_type.value}")

    async def _fallback_to_poll_mode(
        self,
        symbol: str,
        data_type: DataType,
        asset_type: AssetType,
        plugin_id: Optional[str] = None
    ):
        """回退到轮询模式（当 callback 模式不可用时）"""
        logger.info(f"回退到轮询模式: {symbol}, 类型: {data_type.value}")
        try:
            if not plugin_id:
                plugin_id = self._select_default_plugin(data_type)

            plugin = self.realtime_plugins.get(plugin_id)
            if not plugin:
                logger.error(f"回退模式失败：插件 {plugin_id} 未找到")
                return

            if data_type == DataType.TICK_DATA:
                asyncio.create_task(self._poll_tick_data(plugin_id, plugin, [symbol], asset_type))
            elif data_type == DataType.LEVEL2_DATA:
                asyncio.create_task(self._poll_realtime_data(plugin_id, plugin, [symbol], data_type, asset_type))
            elif data_type == DataType.ORDER_BOOK:
                asyncio.create_task(self._poll_order_book_data(plugin_id, plugin, [symbol], asset_type))
            else:
                logger.warning(f"不支持的数据类型: {data_type}")

        except Exception as e:
            logger.error(f"回退到轮询模式失败: {e}")

    def _ensure_callback_mode_started(self):
        """确保 callback 处理协程已启动（线程安全）"""
        with self._callback_mode_lock:
            if not self._callback_mode_started:
                try:
                    loop = asyncio.get_running_loop()
                    self._callback_mode_started = True
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(self._process_callback_queue()))
                    logger.info("Callback 处理协程已启动")
                except RuntimeError:
                    logger.warning("当前无运行中的事件循环，Callback 模式将在首次订阅时启动")

    async def _ensure_callback_mode_started_async(self):
        """异步确保 callback 处理协程已启动"""
        with self._callback_mode_lock:
            if not self._callback_mode_started:
                self._callback_mode_started = True
                asyncio.create_task(self._process_callback_queue())
                logger.info("Callback 处理协程已启动")

    def _queue_callback_data(self, plugin_id: str, symbol: str, data_type: str, data: Any):
        """
        将 callback 数据放入队列（线程安全）

        此方法在插件的 WebSocket/xtdata 线程中被调用
        必须使用线程安全的方式处理
        """
        try:
            self._callback_queue.put_nowait({
                'plugin_id': plugin_id,
                'symbol': symbol,
                'data_type': data_type,
                'data': data,
                'timestamp': time_module.time()
            })
        except queue.Full:
            logger.warning(f"Callback 队列已满，跳过数据: {symbol}")

    async def _process_callback_queue(self):
        """
        处理 callback 队列（持续运行）

        从队列中取出数据，进行标准化和验证，然后发布事件
        """
        logger.info("Callback 队列处理协程启动")

        while self._use_callback_mode:
            try:
                # 非阻塞获取数据
                while not self._callback_queue.empty():
                    try:
                        callback_data = self._callback_queue.get_nowait()
                        await self._process_callback_data(callback_data)
                    except queue.Empty:
                        break

                # 控制处理频率，避免 CPU 空转
                await asyncio.sleep(0.01)  # 10ms 间隔

            except Exception as e:
                logger.error(f"处理 callback 队列失败: {e}")
                await asyncio.sleep(0.1)

    async def _process_callback_data(self, callback_data: Dict):
        """处理单个 callback 数据"""
        try:
            plugin_id = callback_data['plugin_id']
            symbol = callback_data['symbol']
            data_type_str = callback_data['data_type']
            raw_data = callback_data['data']

            # 转换 data_type 字符串到 DataType 枚举
            try:
                data_type = DataType(data_type_str)
            except ValueError:
                data_type = DataType.LEVEL2_DATA  # 默认值

            # 获取插件
            plugin = self.realtime_plugins.get(plugin_id)
            if not plugin:
                logger.warning(f"插件 {plugin_id} 未找到")
                return

            # 将 raw_data 转换为 DataFrame 格式以兼容现有处理逻辑
            if isinstance(raw_data, dict):
                df = pd.DataFrame([raw_data])
            elif isinstance(raw_data, list):
                df = pd.DataFrame(raw_data)
            elif hasattr(raw_data, 'to_dict'):
                df = raw_data.to_dict()
                df = pd.DataFrame(df) if isinstance(df, dict) else raw_data
            else:
                logger.warning(f"Callback 数据格式不支持: {type(raw_data)}")
                return

            if df.empty:
                return

            # 使用现有的 _process_realtime_data 方法处理
            await self._process_realtime_data(plugin_id, df, data_type)

            logger.debug(f"Callback 数据已处理: {symbol}, 类型: {data_type.value}")

        except Exception as e:
            logger.error(f"处理 callback 数据失败: {e}")

    def _select_default_plugin(self, data_type: DataType) -> str:
        """选择默认插件（根据数据类型能力匹配）"""
        if not self.realtime_plugins:
            logger.warning(f"没有已注册的实时数据插件可供选择，数据类型: {data_type.value}")
            return ""

        logger.info(f"当前已注册的实时数据插件: {list(self.realtime_plugins.keys())}")

        capability_map = {
            DataType.TICK_DATA: 'tick',
            DataType.LEVEL2_DATA: 'level2',
            DataType.ORDER_BOOK: 'order_book',
        }
        required_capability = capability_map.get(data_type)
        logger.debug(f"为数据类型 {data_type.value} 查找具有能力 {required_capability} 的插件")

        for plugin_id, plugin in self.realtime_plugins.items():
            if hasattr(plugin, 'get_capabilities'):
                capabilities = plugin.get_capabilities()
                logger.debug(f"插件 {plugin_id} 的能力: {capabilities}")
                if required_capability:
                    if capabilities.get(required_capability, False):
                        logger.info(f"找到匹配的插件: {plugin_id}，能力: {required_capability}")
                        return plugin_id
                    else:
                        logger.debug(f"插件 {plugin_id} 缺少所需能力 {required_capability}，继续寻找")
                        continue
                else:
                    return plugin_id
            else:
                logger.debug(f"插件 {plugin_id} 没有 get_capabilities 方法，直接使用")
                return plugin_id

        if not required_capability:
            first_plugin = next(iter(self.realtime_plugins.keys()), "")
            logger.warning(f"无法精确匹配，回退使用第一个可用插件: {first_plugin}")
            return first_plugin

        logger.warning(f"没有找到支持数据类型 {data_type.value} (需要能力: {required_capability}) 的插件")
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
        """
        订阅 Level-2 数据（智能降级版本）
        
        使用智能降级策略：
        1. Callback 优先（实时推送，延迟 <100ms）
        2. Pull 降级（带缓存轮询，减少 API 调用）
        
        Args:
            plugin_id: 插件 ID
            plugin: 插件实例
            symbols: 股票代码列表
            asset_type: 资产类型
        """
        try:
            for symbol in symbols:
                # 使用智能降级策略
                await self._subscribe_level2_data_smart(symbol, plugin_id, plugin, asset_type)
            
            logger.info(f"Level-2 数据订阅完成（智能降级）：{symbols}, 插件：{plugin_id}")

        except Exception as e:
            logger.error(f"订阅 Level-2 数据失败，插件 {plugin_id}: {e}")
            raise

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
            for standard_data in raw_data.to_dict('records'):

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

                    # 发布成功后清理缓冲区，避免deque+DuckDB双重存储
                    if symbol:
                        self._flush_buffered_data(symbol)

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

                    # 发布成功后清理缓冲区，避免deque+DuckDB双重存储
                    self._flush_buffered_data(symbol)

        except Exception as e:
            logger.error(f"处理Tick数据失败，插件 {plugin_id}: {e}")

    async def _process_level2_data(self, plugin_id: str, symbol: str, level2_data: Dict):
        """
        处理 Level-2 数据
        
        Args:
            plugin_id: 插件 ID
            symbol: 股票代码
            level2_data: Level-2 数据（包含 bids/asks 五档）
        """
        try:
            standard_level2 = level2_data

            if self.data_standardizer:
                standard_level2 = self.data_standardizer.standardize_realtime_data(standard_level2, DataType.LEVEL2_DATA, plugin_id)

            if not standard_level2:
                return

            should_validate = self.data_validator is not None
            is_valid = True
            if should_validate:
                is_valid = self.data_validator.validate_realtime_data(standard_level2, DataType.LEVEL2_DATA)

            if is_valid:
                # 添加到缓冲区
                self.data_buffers[symbol].append(standard_level2)

                # 发布事件（使用 RealtimeDataEvent，因为前端期望这个事件类型）
                # 注意：realtime_data 字典必须包含 symbol 字段，前端从这里获取股票代码
                event = RealtimeDataEvent(
                    realtime_data=standard_level2,
                    symbol=symbol,
                    data_type='level2_data'
                )
                await self.event_bus.publish(event)

                # 发布成功后清理缓冲区，避免deque+DuckDB双重存储
                self._flush_buffered_data(symbol)

                logger.debug(f"Level-2 数据处理完成并发布事件：{symbol}")

        except Exception as e:
            logger.error(f"处理 Level-2 数据失败，插件 {plugin_id}: {e}")
            # 记录错误统计
            if not hasattr(self, '_level2_error_stats'):
                self._level2_error_stats = {}
            if symbol not in self._level2_error_stats:
                self._level2_error_stats[symbol] = {'errors': 0, 'last_error': None}
            self._level2_error_stats[symbol]['errors'] += 1
            self._level2_error_stats[symbol]['last_error'] = str(e)
    
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

                # 发布成功后清理缓冲区，避免deque+DuckDB双重存储
                self._flush_buffered_data(symbol)

        except Exception as e:
            logger.error(f"处理订单簿数据失败，插件 {plugin_id}: {e}")

    def get_tick_data(self, symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        获取指定时间范围内的tick级别历史数据
        从DuckDB或其他历史数据库中查询
        """
        logger.info(f"从历史数据源获取tick数据: {symbol} 从 {start_time} 到 {end_time}")

        try:
            manager = get_connection_manager()
            query = """
                SELECT symbol, timestamp, price, volume, trade_type, source
                FROM tick_data 
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """

            with manager.get_connection(MAIN_DATABASE_PATH) as conn:
                result_df = conn.execute(query, [symbol, start_time.isoformat(), end_time.isoformat()]).fetchdf()

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
            manager = get_connection_manager()
            query = """
                SELECT symbol, timestamp, bids, asks, source
                FROM order_book_snapshots 
                WHERE symbol = ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """

            with manager.get_connection(MAIN_DATABASE_PATH) as conn:
                result = conn.execute(query, [symbol, timestamp.isoformat()]).fetchone()

            if result is not None:
                return {
                    "symbol": result['symbol'],
                    "timestamp": result['timestamp'],
                    "bids": json.loads(result['bids']) if isinstance(result['bids'], str) else result['bids'],
                    "asks": json.loads(result['asks']) if isinstance(result['asks'], str) else result['asks'],
                    "source": result['source']
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

    def _flush_buffered_data(self, symbol: str, keep_last: int = 10) -> None:
        """
        清理指定symbol的缓冲区数据，保留最近keep_last条记录

        数据已通过EventBus发布给DuckDB持久化子系统，缓冲区仅作临时缓存。
        清理避免deque+DuckDB双重存储导致的内存浪费。

        Args:
            symbol: 股票代码
            keep_last: 保留最近N条记录，默认10条用于前端获取最近数据
        """
        buffer = self.data_buffers.get(symbol)
        if buffer is not None and len(buffer) > keep_last:
            while len(buffer) > keep_last:
                buffer.popleft()
            logger.debug(f"已清理 {symbol} 缓冲区，保留最近 {keep_last} 条记录")
    
    # ========== 监控和统计方法 ==========
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计字典
        """
        with self._cache_lock:
            current_time = datetime.now()
            valid_count = 0
            expired_count = 0
            
            for symbol, timestamp in self._cache_timestamps.items():
                age = (current_time - timestamp).total_seconds()
                if age > self._cache_ttl_seconds:
                    expired_count += 1
                else:
                    valid_count += 1
            
            return {
                'total_cached': len(self._level2_cache),
                'valid_cache': valid_count,
                'expired_cache': expired_count,
                'cache_ttl_seconds': self._cache_ttl_seconds,
                'cache_size_mb': len(self._level2_cache) * 0.001  # 估算
            }
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """
        获取降级统计信息
        
        Returns:
            降级统计字典
        """
        total_fallbacks = sum(stats['total_fallbacks'] for stats in self._fallback_stats.values())
        callback_failures = sum(stats.get('callback_failures', 0) for stats in self._fallback_stats.values())
        
        return {
            'total_symbols': len(self._fallback_stats),
            'total_fallbacks': total_fallbacks,
            'callback_failures': callback_failures,
            'fallback_rate': callback_failures / total_fallbacks if total_fallbacks > 0 else 0,
            'details': {
                symbol: {
                    'total_fallbacks': stats['total_fallbacks'],
                    'last_reasons': stats['reasons'][-5:]  # 最近 5 次原因
                }
                for symbol, stats in self._fallback_stats.items()
            }
        }
    
    def get_polling_stats(self) -> Dict[str, Any]:
        """
        获取轮询统计信息
        
        Returns:
            轮询统计字典
        """
        current_time = datetime.now()
        polling_info = {}
        
        for symbol, last_poll in self._last_poll_times.items():
            interval = self._poll_intervals.get(symbol, 1.0)
            time_since_last = (current_time - last_poll).total_seconds()
            
            polling_info[symbol] = {
                'last_poll': last_poll.isoformat(),
                'seconds_ago': time_since_last,
                'current_interval': interval,
                'next_poll_in': max(0, interval - time_since_last)
            }
        
        return {
            'total_polling_symbols': len(polling_info),
            'polling_details': polling_info
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            性能指标字典
        """
        cache_stats = self.get_cache_stats()
        fallback_stats = self.get_fallback_stats()
        polling_stats = self.get_polling_stats()
        
        return {
            'cache': cache_stats,
            'fallback': fallback_stats,
            'polling': polling_stats,
            'summary': {
                'callback_success_rate': 1 - fallback_stats['fallback_rate'],
                'cache_hit_rate': cache_stats['valid_cache'] / max(1, cache_stats['total_cached']),
                'total_realtime_symbols': len(self.data_buffers)
            }
        }

    # ========== Level-2 数据缓存管理方法 ==========
    
    def _get_cached_level2_data(self, symbol: str) -> Optional[Dict]:
        """
        获取缓存的 Level-2 数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            缓存的数据，如果缓存不存在或已过期则返回 None
        """
        with self._cache_lock:
            if symbol not in self._level2_cache:
                return None
            
            # 检查缓存是否过期
            timestamp = self._cache_timestamps.get(symbol)
            if not timestamp:
                return None
            
            age = (datetime.now() - timestamp).total_seconds()
            if age > self._cache_ttl_seconds:
                # 缓存过期，清理
                logger.debug(f"缓存过期：{symbol}, 年龄：{age:.2f}s")
                del self._level2_cache[symbol]
                del self._cache_timestamps[symbol]
                return None
            
            # 缓存有效
            logger.debug(f"缓存命中：{symbol}, 年龄：{age:.2f}s")
            return self._level2_cache[symbol]
    
    def _set_cached_level2_data(self, symbol: str, data: Dict):
        """
        设置缓存的 Level-2 数据
        
        Args:
            symbol: 股票代码
            data: Level-2 数据
        """
        with self._cache_lock:
            self._level2_cache[symbol] = data
            self._cache_timestamps[symbol] = datetime.now()
            logger.debug(f"缓存更新：{symbol}")
    
    def _record_fallback(self, symbol: str, reason: str):
        """
        记录降级事件
        
        Args:
            symbol: 股票代码
            reason: 降级原因
        """
        if symbol not in self._fallback_stats:
            self._fallback_stats[symbol] = {
                'total_fallbacks': 0,
                'callback_failures': 0,
                'pull_failures': 0,
                'reasons': []
            }
        
        self._fallback_stats[symbol]['total_fallbacks'] += 1
        self._fallback_stats[symbol]['reasons'].append(reason)
        
        logger.warning(f"降级记录：{symbol}, 原因：{reason}, 总次数：{self._fallback_stats[symbol]['total_fallbacks']}")
    
    # ========== 智能降级策略方法 ==========
    
    async def _subscribe_level2_data_smart(
        self,
        symbol: str,
        plugin_id: str,
        plugin: IDataSourcePlugin,
        asset_type: AssetType
    ):
        """
        智能订阅 Level-2 数据：Callback 优先，Pull 降级
        
        策略：
        1. 首先尝试获取初始数据（Pull 模式）
        2. 然后注册 Callback（实时推送）
        3. 如果 Callback 失败，降级到带缓存的轮询
        
        Args:
            symbol: 股票代码
            plugin_id: 插件 ID
            plugin: 插件实例
            asset_type: 资产类型
        """
        logger.info(f"智能订阅 Level-2: {symbol}, 插件：{plugin_id}")
        
        # 步骤 1: 获取初始数据（Pull 模式）
        try:
            if hasattr(plugin, 'get_level2_data'):
                initial_data = plugin.get_level2_data(symbol)
                if initial_data:
                    # 标准化并处理数据
                    await self._process_level2_data(plugin_id, symbol, initial_data)
                    # 更新缓存
                    self._set_cached_level2_data(symbol, initial_data)
                    logger.info(f"✅ 初始数据获取成功：{symbol}")
                else:
                    logger.warning(f"⚠️ 初始数据为空：{symbol}")
            else:
                logger.warning(f"插件 {plugin_id} 没有 get_level2_data 方法")
        except Exception as e:
            logger.error(f"❌ 获取初始数据失败：{symbol}, {e}")
            self._record_fallback(symbol, f"initial_pull_failed: {e}")
        
        # 步骤 2: 注册 Callback（实时推送）
        try:
            # 创建 callback 适配器
            adapter = PluginCallbackAdapter(self, plugin_id, DataType.LEVEL2_DATA)
            
            # 调用插件的 subscribe_realtime_data 方法注册 callback
            success = plugin.subscribe_realtime_data([symbol], adapter, DataType.LEVEL2_DATA)
            
            if success:
                logger.info(f"✅ Callback 模式订阅成功：{symbol}")
                # 记录成功，重置降级统计
                if symbol in self._fallback_stats:
                    self._fallback_stats[symbol]['total_fallbacks'] = 0
                return
            else:
                logger.warning(f"⚠️ Callback 模式返回失败：{symbol}")
                self._record_fallback(symbol, "callback_returned_false")
                
        except Exception as e:
            logger.error(f"❌ Callback 模式异常：{symbol}, {e}")
            self._record_fallback(symbol, f"callback_exception: {e}")
        
        # 步骤 3: 降级到带缓存的轮询
        logger.warning(f"⚠️ Callback 失败，降级到带缓存的轮询：{symbol}")
        self._record_fallback(symbol, "fallback_to_polling")
        
        # 启动轮询任务（带缓存）
        asyncio.create_task(self._poll_level2_data_cached(plugin_id, plugin, [symbol], asset_type))
    
    async def _poll_level2_data_cached(
        self,
        plugin_id: str,
        plugin: IDataSourcePlugin,
        symbols: List[str],
        asset_type: AssetType,
        initial_interval: float = 1.0,
        max_interval: float = 5.0,
        min_interval: float = 0.5  # 最小轮询间隔保护
    ):
        """
        带缓存的 Level-2 轮询方法
        
        特点：
        - 使用动态轮询间隔（指数退避）
        - 只在缓存过期时拉取
        - 减少 API 调用次数
        - 添加最小间隔保护防止过频请求
        - 添加错误计数和重试限制
        
        Args:
            plugin_id: 插件 ID
            plugin: 插件实例
            symbols: 股票代码列表
            asset_type: 资产类型
            initial_interval: 初始轮询间隔（秒）
            max_interval: 最大轮询间隔（秒）
            min_interval: 最小轮询间隔（秒），防止过频请求
        """
        logger.info(f"启动带缓存的轮询：{symbols}, 插件：{plugin_id}")
        
        # 初始化轮询参数
        for symbol in symbols:
            self._poll_intervals[symbol] = max(initial_interval, min_interval)
            # 添加错误计数器
            if not hasattr(self, '_poll_error_counts'):
                self._poll_error_counts = {}
            if symbol not in self._poll_error_counts:
                self._poll_error_counts[symbol] = 0
        
        consecutive_errors = 0
        max_consecutive_errors = 10  # 最大连续错误次数
        
        while True:
            try:
                current_time = datetime.now()
                
                for symbol in symbols:
                    # 检查是否需要轮询
                    last_poll = self._last_poll_times.get(symbol)
                    interval = self._poll_intervals.get(symbol, initial_interval)
                    
                    # 确保间隔不小于最小值
                    interval = max(interval, min_interval)
                    
                    if last_poll and (current_time - last_poll).total_seconds() < interval:
                        # 还没到轮询时间
                        continue
                    
                    # 检查缓存是否有效
                    cached_data = self._get_cached_level2_data(symbol)
                    if cached_data:
                        # 缓存有效，跳过本次轮询
                        logger.debug(f"缓存有效，跳过轮询：{symbol}")
                        # 重置错误计数
                        if symbol in self._poll_error_counts:
                            self._poll_error_counts[symbol] = 0
                        continue
                    
                    # 执行轮询
                    try:
                        if hasattr(plugin, 'get_level2_data'):
                            data = plugin.get_level2_data(symbol)
                            if data:
                                # 更新缓存
                                self._set_cached_level2_data(symbol, data)
                                # 处理数据
                                await self._process_level2_data(plugin_id, symbol, data)
                                # 重置轮询间隔和错误计数（成功）
                                self._poll_intervals[symbol] = max(initial_interval, min_interval)
                                consecutive_errors = 0
                                if symbol in self._poll_error_counts:
                                    self._poll_error_counts[symbol] = 0
                                logger.debug(f"轮询成功：{symbol}")
                            else:
                                # 数据为空，增加轮询间隔（指数退避）
                                consecutive_errors += 1
                                self._poll_intervals[symbol] = min(
                                    self._poll_intervals.get(symbol, initial_interval) * 1.5,
                                    max_interval
                                )
                                logger.warning(f"轮询数据为空：{symbol}, 连续错误：{consecutive_errors}, 下次间隔：{self._poll_intervals[symbol]:.2f}s")
                        else:
                            logger.error(f"插件 {plugin_id} 没有 get_level2_data 方法")
                            consecutive_errors += 1
                    except Exception as poll_error:
                        # 轮询异常
                        consecutive_errors += 1
                        if symbol in self._poll_error_counts:
                            self._poll_error_counts[symbol] += 1
                        logger.error(f"轮询异常：{symbol}, 错误：{poll_error}, 连续错误：{consecutive_errors}")
                        
                        # 增加轮询间隔
                        self._poll_intervals[symbol] = min(
                            self._poll_intervals.get(symbol, initial_interval) * 2,
                            max_interval
                        )
                    
                    # 记录上次轮询时间
                    self._last_poll_times[symbol] = current_time
                    
                    # 检查是否超过最大连续错误次数
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"连续错误次数超限（{max_consecutive_errors}），停止轮询：{symbol}")
                        # 发送告警事件
                        from core.events.types import ErrorEvent
                        await self.event_bus.publish(ErrorEvent(
                            error_type='level2_polling_max_errors',
                            message=f'股票 {symbol} 连续轮询失败 {consecutive_errors} 次，已停止轮询',
                            symbol=symbol
                        ))
                        return  # 退出轮询
                
                
                # 等待 100ms 后检查下次轮询
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info(f"轮询任务被取消：{symbols}")
                break
            except Exception as e:
                logger.error(f"轮询异常：{e}")
                # 异常后等待更长时间
                await asyncio.sleep(5.0)
    
    async def cleanup(self):
        """清理资源"""
        logger.info("开始清理实时数据管理器资源...")

        # 停止所有订阅
        for plugin_id in self.subscription_status:
            for subscription_key in self.subscription_status[plugin_id]:
                self.subscription_status[plugin_id][subscription_key] = False

        # 关闭 WebSocket 连接
        for connection in self.websocket_connections.values():
            try:
                if hasattr(connection, 'close'):
                    connection.close()
            except Exception as e:
                logger.warning(f"关闭 WebSocket 连接失败：{e}")

        self.websocket_connections.clear()
        
        # 清理缓存
        with self._cache_lock:
            self._level2_cache.clear()
            self._cache_timestamps.clear()
        
        logger.info("实时数据管理器资源清理完成")
