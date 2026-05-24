#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket实时数据流客户端

提供高性能的WebSocket实时数据流处理，支持增量数据更新和数据压缩

作者: FactorWeave-Quant团队
版本: 1.0
"""

import asyncio
import json
import gzip
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
from loguru import logger
import websockets
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSING = "closing"

class DataPriority(Enum):
    """数据优先级"""
    CRITICAL = 1      # 关键数据（交易信号等）
    HIGH = 2          # 高优先级（实时价格等）
    NORMAL = 3        # 普通数据（技术指标等）
    LOW = 4           # 低优先级（历史数据等）

@dataclass
class DataMessage:
    """数据消息"""
    id: str
    type: str
    data: Any
    timestamp: float
    priority: DataPriority = DataPriority.NORMAL
    compressed: bool = False
    source: str = "websocket"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConnectionConfig:
    """连接配置"""
    url: str
    heartbeat_interval: float = 30.0  # 心跳间隔（秒）
    reconnect_attempts: int = 5       # 重连次数
    reconnect_delay: float = 1.0      # 重连延迟（秒）
    max_reconnect_delay: float = 60.0 # 最大重连延迟
    backoff_factor: float = 2.0       # 退避因子
    timeout: float = 10.0             # 连接超时
    max_message_size: int = 10 * 1024 * 1024  # 最大消息大小（10MB）
    compression: bool = True          # 是否启用压缩
    
    # 认证配置
    auth_token: Optional[str] = None
    api_key: Optional[str] = None
    secret_key: Optional[str] = None

class MessageQueue:
    """优先级消息队列"""
    
    def __init__(self, max_size: int = 10000):
        self.queues = {
            DataPriority.CRITICAL: asyncio.Queue(maxsize=max_size),
            DataPriority.HIGH: asyncio.Queue(maxsize=max_size),
            DataPriority.NORMAL: asyncio.Queue(maxsize=max_size),
            DataPriority.LOW: asyncio.Queue(maxsize=max_size)
        }
        self._lock = asyncio.Lock()
        
    async def put(self, message: DataMessage):
        """放入消息"""
        async with self._lock:
            await self.queues[message.priority].put(message)
    
    async def get(self) -> DataMessage:
        """获取消息（按优先级）"""
        # 先检查高优先级队列
        for priority in [DataPriority.CRITICAL, DataPriority.HIGH, DataPriority.NORMAL, DataPriority.LOW]:
            queue = self.queues[priority]
            try:
                if not queue.empty():
                    return queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
        
        # 如果没有消息，等待
        await self.queues[DataPriority.NORMAL].get()
    
    async def qsize(self) -> int:
        """获取队列大小"""
        return sum(queue.qsize() for queue in self.queues.values())
    
    def get_priority_sizes(self) -> Dict[DataPriority, int]:
        """获取各优先级队列大小"""
        return {priority: queue.qsize() for priority, queue in self.queues.items()}

class DataCompressor:
    """数据压缩器"""
    
    @staticmethod
    def compress_data(data: Any) -> bytes:
        """压缩数据"""
        try:
            json_data = json.dumps(data, default=str).encode('utf-8')
            return gzip.compress(json_data)
        except Exception as e:
            logger.warning(f"数据压缩失败: {e}")
            return json.dumps(data, default=str).encode('utf-8')
    
    @staticmethod
    def decompress_data(compressed_data: bytes) -> Any:
        """解压数据"""
        try:
            decompressed = gzip.decompress(compressed_data)
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            logger.warning(f"数据解压失败: {e}")
            return json.loads(compressed_data.decode('utf-8'))

class RealTimeDataProcessor(QObject):
    """实时数据处理器"""
    
    # 信号定义
    data_received = pyqtSignal(str, object)  # message_id, data
    connection_state_changed = pyqtSignal(str, str)  # old_state, new_state
    performance_metrics = pyqtSignal(dict)  # 性能指标
    error_occurred = pyqtSignal(str, str)  # error_type, error_message
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        super().__init__()
        self.config = config or ConnectionConfig("ws://localhost:8080")
        self.state = ConnectionState.DISCONNECTED
        self.websocket = None
        self._listen_task = None
        self.message_queue = MessageQueue()
        self.data_processors: Dict[str, Callable] = {}
        
        # 性能统计
        self.stats = {
            'messages_received': 0,
            'messages_processed': 0,
            'bytes_received': 0,
            'connection_timeouts': 0,
            'compression_ratio': 0.0,
            'avg_processing_time_ms': 0.0,
            'last_heartbeat': 0,
            'reconnect_count': 0
        }
        
        # 监控定时器
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._send_heartbeat)
        self.heartbeat_timer.start(int(self.config.heartbeat_interval * 1000))
        
        # 统计定时器
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._emit_performance_metrics)
        self.stats_timer.start(5000)  # 每5秒发送一次性能统计
        
        # 处理定时器
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self._process_messages)
        self.processing_timer.start(16)  # 60fps处理
        
        self._processing_times = deque(maxlen=100)
    
    async def connect(self):
        """连接WebSocket"""
        if self.state in [ConnectionState.CONNECTING, ConnectionState.CONNECTED]:
            return
        
        self._change_state(ConnectionState.CONNECTING)
        
        try:
            # 构建连接参数
            extra_headers = {}
            if self.config.auth_token:
                extra_headers['Authorization'] = f"Bearer {self.config.auth_token}"
            
            ssl_context = None
            if self.config.url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
            
            # 建立连接
            self.websocket = await websockets.connect(
                self.config.url,
                extra_headers=extra_headers,
                ssl=ssl_context,
                max_size=self.config.max_message_size,
                ping_interval=None  # 使用自定义心跳
            )
            
            self._change_state(ConnectionState.CONNECTED)
            self.stats['reconnect_count'] = 0

            if self._listen_task and not self._listen_task.done():
                self._listen_task.cancel()
            self._listen_task = asyncio.create_task(self._listen_messages())

            await self._send_initial_messages()
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            self._change_state(ConnectionState.FAILED)
            await self._handle_connection_error(e)
    
    async def disconnect(self):
        """断开连接"""
        self._change_state(ConnectionState.CLOSING)

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        self._change_state(ConnectionState.DISCONNECTED)
    
    async def _listen_messages(self):
        """监听消息"""
        try:
            async for message in self.websocket:
                try:
                    # 更新统计
                    self.stats['messages_received'] += 1
                    self.stats['bytes_received'] += len(message)
                    
                    # 解析消息
                    data = self._parse_message(message)
                    
                    # 创建数据消息
                    data_message = DataMessage(
                        id=str(time.time()),
                        type=data.get('type', 'unknown'),
                        data=data,
                        timestamp=time.time(),
                        priority=self._determine_priority(data),
                        compressed=data.get('compressed', False),
                        source='websocket'
                    )
                    
                    # 添加到队列
                    await self.message_queue.put(data_message)
                    
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    self.error_occurred.emit("message_processing", str(e))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket连接已关闭")
            await self._reconnect()
        except Exception as e:
            logger.error(f"消息监听错误: {e}")
            await self._reconnect()
    
    def _parse_message(self, message: str) -> Dict[str, Any]:
        """解析消息"""
        try:
            data = json.loads(message)
            
            # 检查是否需要解压
            if data.get('compressed', False) and 'compressed_data' in data:
                data['data'] = DataCompressor.decompress_data(
                    bytes.fromhex(data['compressed_data']))
                data['compressed'] = True
            
            return data
            
        except Exception as e:
            logger.error(f"消息解析失败: {e}")
            return {'type': 'error', 'data': message}
    
    def _determine_priority(self, data: Dict[str, Any]) -> DataPriority:
        """确定消息优先级"""
        msg_type = data.get('type', '').lower()
        
        if msg_type in ['trade_signal', 'critical_alert', 'emergency']:
            return DataPriority.CRITICAL
        elif msg_type in ['price_update', 'order_update', 'position_change']:
            return DataPriority.HIGH
        elif msg_type in ['indicator_update', 'market_data']:
            return DataPriority.NORMAL
        else:
            return DataPriority.LOW
    
    def register_processor(self, message_type: str, processor: Callable):
        """注册数据处理器"""
        self.data_processors[message_type] = processor
    
    def _process_messages(self):
        """处理消息（主线程）"""
        processing_start = time.time()
        
        try:
            # 获取队列大小
            queue_size = self.message_queue.qsize()
            
            # 处理有限数量的消息，避免阻塞UI
            processed_count = 0
            max_processing_per_tick = 100
            
            while queue_size > 0 and processed_count < max_processing_per_tick:
                try:
                    # 异步获取消息
                    future = asyncio.run_coroutine_threadsafe(
                        self.message_queue.get(), self._get_loop()
                    )
                    message = future.result(timeout=0.001)
                    
                    # 处理消息
                    self._handle_message(message)
                    processed_count += 1
                    
                except (asyncio.TimeoutError, asyncio.QueueEmpty):
                    break
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    break
            
            # 更新统计
            if processed_count > 0:
                self.stats['messages_processed'] += processed_count
                processing_time = (time.time() - processing_start) * 1000
                self._processing_times.append(processing_time)
                
                # 计算平均处理时间
                if self._processing_times:
                    self.stats['avg_processing_time_ms'] = sum(self._processing_times) / len(self._processing_times)
        
        except Exception as e:
            logger.error(f"消息处理循环错误: {e}")
    
    def _handle_message(self, message: DataMessage):
        """处理单个消息"""
        try:
            # 查找对应的处理器
            processor = self.data_processors.get(message.type)
            
            if processor:
                # 在线程池中执行处理器
                loop = self._get_loop()
                future = asyncio.run_coroutine_threadsafe(
                    processor(message.data), loop
                )
                future.result(timeout=1.0)  # 1秒超时
            
            # 发送信号
            self.data_received.emit(message.id, message.data)
            
        except Exception as e:
            logger.error(f"处理消息失败 {message.type}: {e}")
            self.error_occurred.emit("message_handle", str(e))
    
    async def _send_initial_messages(self):
        """发送初始连接消息"""
        try:
            if self.config.auth_token:
                auth_message = {
                    'type': 'auth',
                    'token': self.config.auth_token,
                    'timestamp': time.time()
                }
                await self.websocket.send(json.dumps(auth_message))
        except Exception as e:
            logger.error(f"发送初始消息失败: {e}")
    
    def _send_heartbeat(self):
        """发送心跳"""
        if self.state == ConnectionState.CONNECTED and self.websocket:
            try:
                # 创建心跳消息
                heartbeat = {
                    'type': 'heartbeat',
                    'timestamp': time.time(),
                    'sequence': self.stats['messages_received']
                }
                
                # 发送心跳
                loop = self._get_loop()
                future = asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps(heartbeat)), loop
                )
                future.result(timeout=5.0)
                
                self.stats['last_heartbeat'] = time.time()
                
            except Exception as e:
                logger.warning(f"发送心跳失败: {e}")
    
    async def _reconnect(self):
        """重连逻辑"""
        if self.state == ConnectionState.RECONNECTING:
            return
        
        self._change_state(ConnectionState.RECONNECTING)
        
        attempt = 0
        delay = self.config.reconnect_delay
        
        while attempt < self.config.reconnect_attempts:
            attempt += 1
            logger.info(f"尝试重连WebSocket ({attempt}/{self.config.reconnect_attempts})")
            
            try:
                await asyncio.sleep(delay)
                await self.connect()
                return  # 重连成功
                
            except Exception as e:
                logger.warning(f"重连失败 (尝试 {attempt}): {e}")
                delay = min(delay * self.config.backoff_factor, self.config.max_reconnect_delay)
        
        # 重连失败
        self._change_state(ConnectionState.FAILED)
        self.stats['connection_timeouts'] += 1
    
    async def _handle_connection_error(self, error: Exception):
        """处理连接错误"""
        self.error_occurred.emit("connection", str(error))
        await self._reconnect()
    
    def _change_state(self, new_state: ConnectionState):
        """改变连接状态"""
        old_state = self.state
        self.state = new_state
        self.connection_state_changed.emit(old_state.value, new_state.value)
        logger.info(f"连接状态变更: {old_state.value} -> {new_state.value}")
    
    def _emit_performance_metrics(self):
        """发送性能指标"""
        metrics = {
            'connection_state': self.state.value,
            'messages_received_per_sec': self.stats['messages_received'] / 5,  # 5秒统计
            'messages_processed_per_sec': self.stats['messages_processed'] / 5,
            'avg_processing_time_ms': self.stats['avg_processing_time_ms'],
            'queue_size': self.message_queue.qsize(),
            'queue_sizes': {p.name: size for p, size in self.message_queue.get_priority_sizes().items()},
            'bytes_per_sec': self.stats['bytes_received'] / 5,
            'reconnect_count': self.stats['reconnect_count'],
            'last_heartbeat_ago': time.time() - self.stats['last_heartbeat'] if self.stats['last_heartbeat'] > 0 else 0
        }
        
        self.performance_metrics.emit(metrics)
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """获取事件循环"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    async def send_message(self, message_type: str, data: Any):
        """发送消息"""
        if self.state != ConnectionState.CONNECTED or not self.websocket:
            logger.warning("WebSocket未连接，无法发送消息")
            return
        
        try:
            message = {
                'type': message_type,
                'data': data,
                'timestamp': time.time()
            }
            
            # 压缩大数据
            message_str = json.dumps(message, default=str)
            if self.config.compression and len(message_str) > 1024:
                compressed_data = DataCompressor.compress_data(data)
                message = {
                    'type': message_type,
                    'compressed_data': compressed_data.hex(),
                    'compressed': True,
                    'timestamp': time.time()
                }
                message_str = json.dumps(message)
            
            await self.websocket.send(message_str)
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def cleanup(self):
        """清理资源"""
        self.heartbeat_timer.stop()
        self.stats_timer.stop()
        self.processing_timer.stop()
        
        # 关闭WebSocket连接
        if self.websocket:
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(self.disconnect(), loop)

# 便捷函数
def create_realtime_processor(url: str, **kwargs) -> RealTimeDataProcessor:
    """创建实时数据处理器"""
    config = ConnectionConfig(url=url, **kwargs)
    return RealTimeDataProcessor(config)

# 常用WebSocket处理器
def create_trading_processor() -> RealTimeDataProcessor:
    """创建交易专用处理器"""
    config = ConnectionConfig(
        url="wss://api.example.com/trading",
        heartbeat_interval=15.0,
        reconnect_attempts=10,
        compression=True
    )
    
    processor = RealTimeDataProcessor(config)
    
    # 注册处理器
    async def handle_price_update(data):
        logger.debug(f"价格更新: {data}")
    
    async def handle_trade_signal(data):
        logger.info(f"交易信号: {data}")
    
    processor.register_processor("price_update", handle_price_update)
    processor.register_processor("trade_signal", handle_trade_signal)
    
    return processor